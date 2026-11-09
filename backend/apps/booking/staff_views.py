from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffRole

from .models import Booking
from .outcomes import mark_outcome
from .services import BookingError


class OutcomeSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=["visited", "no_show"])


class VisitOutcomeView(APIView):
    permission_classes = [IsStaffRole]

    def post(self, request, booking_id):
        s = OutcomeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        booking = get_object_or_404(Booking.objects.select_related("slot"), pk=booking_id)
        if not (request.user.is_head or booking.slot.executive_id == request.user.id):
            return Response({"detail": "Not your visit."}, status=403)
        try:
            updated = mark_outcome(booking_id=booking.id, outcome=s.validated_data["outcome"])
        except BookingError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response({"id": updated.id, "status": updated.status})