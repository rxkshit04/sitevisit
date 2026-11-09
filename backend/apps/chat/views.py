from django.db.models import F, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsHead, IsStaffRole
from apps.booking import services as booking_services
from apps.booking.models import Booking, Slot
from apps.leads.models import Lead
from apps.leads.tokens import read_lead_token
from apps.messaging.models import OutboxMessage
from apps.messaging.services import queue_booking_message

from . import agent
from .handoff import handoff_payload
from .models import ChatMessage, Conversation, FactEntry, Handoff
from .tools import booking_payload, exec_name, slot_label


class PublicChatThrottle(AnonRateThrottle):
    scope = "public_chat"
    rate = "60/hour"


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=500)


class ChatInSerializer(TokenSerializer):
    message = serializers.CharField(max_length=1000)


class BookInSerializer(TokenSerializer):
    slot_id = serializers.IntegerField(min_value=1)


def get_lead(token):
    lead_id = read_lead_token(str(token))
    if lead_id is None:
        return None
    return Lead.objects.select_related("project").filter(pk=lead_id).first()


def current_booking(lead):
    return (
        Booking.objects.filter(lead=lead, status=Booking.Status.CONFIRMED)
        .select_related("slot__executive", "slot__project")
        .first()
    )


EXPIRED = {"detail": "This chat link has expired. Please start again."}


class PublicView(APIView):
    """Buyers have no accounts: a signed token from the intake step identifies the lead."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicChatThrottle]
    serializer_class = TokenSerializer

    def post(self, request):
        s = self.serializer_class(data=request.data)
        s.is_valid(raise_exception=True)
        lead = get_lead(s.validated_data["token"])
        if lead is None:
            return Response(EXPIRED, status=404)
        return self.handle(lead, s.validated_data)


class ChatView(PublicView):
    serializer_class = ChatInSerializer

    def get(self, request):
        lead = get_lead(request.query_params.get("token", ""))
        if lead is None:
            return Response(EXPIRED, status=404)
        p = lead.project
        conv = Conversation.objects.filter(lead=lead).first()
        messages = (
            [
                {"role": m.role, "content": m.content, "at": m.created_at.isoformat()}
                for m in conv.messages.order_by("-id")[:100][::-1]
            ]
            if conv
            else []
        )
        booking = current_booking(lead)
        handoff = Handoff.objects.filter(lead=lead).select_related("executive").order_by("-id").first()
        return Response(
            {
                "project": {
                    "id": p.id,
                    "name": p.name,
                    "rera_number": p.rera_number,
                    "address": p.address,
                },
                "language": lead.language,
                "messages": messages,
                "booking": booking_payload(booking) if booking else None,
                "handoff": handoff_payload(handoff) if handoff else None,
            }
        )

    def handle(self, lead, data):
        return Response(agent.handle_buyer_message(lead, data["message"]))


class HandoffView(PublicView):
    def handle(self, lead, data):
        return Response(agent.request_person(lead))


class BookView(PublicView):
    """Tap-a-slot booking. Books, or moves an existing visit, without going through the model."""

    serializer_class = BookInSerializer

    def handle(self, lead, data):
        slot = Slot.objects.select_related("executive", "project").filter(
            pk=data["slot_id"], project_id=lead.project_id
        ).first()
        if slot is None:
            return Response({"detail": "That slot is not available."}, status=409)
        try:
            try:
                booking = booking_services.book_slot(lead_id=lead.id, slot_id=slot.id)
            except booking_services.AlreadyBooked:
                booking = booking_services.reschedule_booking(lead_id=lead.id, new_slot_id=slot.id)
        except booking_services.BookingError as exc:
            return Response({"detail": str(exc)}, status=409)
        queue_booking_message(booking, OutboxMessage.Kind.CONFIRMATION)
        conv, _ = Conversation.objects.get_or_create(lead=lead)
        agent.save_assistant(conv, f"Visit booked: {slot_label(slot)} with {exec_name(slot.executive)}.")
        return Response({"booking": booking_payload(booking)})


class CancelView(PublicView):
    def handle(self, lead, data):
        booking = current_booking(lead)
        if booking is None:
            return Response({"detail": "There is no upcoming visit to cancel."}, status=409)
        try:
            booking_services.cancel_booking(booking_id=booking.id)
        except booking_services.BookingError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response({"cancelled": True})


# ---- staff -----------------------------------------------------------------


class LeadChatView(APIView):
    permission_classes = [IsStaffRole]

    def get(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        if not (request.user.is_head or lead.assigned_to_id == request.user.id):
            return Response({"detail": "Not your lead."}, status=403)
        conv = Conversation.objects.filter(lead=lead).first()
        if conv is None:
            return Response({"messages": [], "needs": {}, "handoffs": [], "flagged": False, "flag_reason": ""})
        handoffs = Handoff.objects.filter(conversation=conv).select_related("executive").order_by("-id")
        return Response(
            {
                "messages": [
                    {"role": m.role, "content": m.content, "cited": m.cited, "at": m.created_at.isoformat()}
                    for m in conv.messages.all()
                ],
                "needs": conv.needs,
                "flagged": conv.flagged,
                "flag_reason": conv.flag_reason,
                "handoffs": [
                    {
                        "executive_name": exec_name(h.executive),
                        "reason": h.reason,
                        "summary": h.summary,
                        "at": h.created_at.isoformat(),
                    }
                    for h in handoffs
                ],
            }
        )


class FlaggedChatsView(APIView):
    permission_classes = [IsHead]

    def get(self, request):
        last_buyer = ChatMessage.objects.filter(
            conversation=OuterRef("pk"), role=ChatMessage.Role.BUYER
        ).order_by("-id")
        last_summary = Handoff.objects.filter(conversation=OuterRef("pk")).order_by("-id")
        qs = (
            Conversation.objects.filter(flagged=True)
            .select_related("lead__project")
            .annotate(
                last_message=Subquery(last_buyer.values("content")[:1]),
                summary=Subquery(last_summary.values("summary")[:1]),
            )
        )
        if request.query_params.get("reviewed") == "0":
            qs = qs.filter(reviewed_at__isnull=True)
        qs = qs.order_by(F("reviewed_at").asc(nulls_first=True), "-updated_at")[:100]
        return Response(
            [
                {
                    "id": c.id,
                    "lead_id": c.lead_id,
                    "lead_name": c.lead.name,
                    "project": c.lead.project.name,
                    "reason": c.flag_reason,
                    "reviewed": c.reviewed_at is not None,
                    "summary": c.summary or "",
                    "last_message": c.last_message or "",
                    "updated_at": c.updated_at.isoformat(),
                }
                for c in qs
            ]
        )


class ReviewChatView(APIView):
    permission_classes = [IsHead]

    def post(self, request, conversation_id):
        conv = get_object_or_404(Conversation, pk=conversation_id)
        conv.reviewed_at = timezone.now()
        conv.save(update_fields=["reviewed_at", "updated_at"])
        return Response({"id": conv.id, "reviewed": True})


class FactSerializer(serializers.ModelSerializer):
    class Meta:
        model = FactEntry
        fields = ["id", "project", "title", "text", "is_registered", "updated_at"]
        read_only_fields = ["id", "updated_at"]
        extra_kwargs = {"text": {"max_length": 600}}


class FactListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsHead]
    serializer_class = FactSerializer

    def get_queryset(self):
        qs = FactEntry.objects.all()
        pid = self.request.query_params.get("project", "")
        return qs.filter(project_id=int(pid)) if pid.isdigit() else qs


class FactDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsHead]
    serializer_class = FactSerializer
    queryset = FactEntry.objects.all()
    lookup_url_kwarg = "fact_id"