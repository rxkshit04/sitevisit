from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffRole
from apps.booking.models import Booking

from .models import Lead
from .serializers import LeadSerializer


class LeadDetailView(APIView):
    permission_classes = [IsStaffRole]

    def get(self, request, lead_id):
        lead = get_object_or_404(
            Lead.objects.select_related("project", "assigned_to").prefetch_related(
                Prefetch("bookings", queryset=Booking.objects.select_related("slot"))
            ),
            pk=lead_id,
        )
        if not (request.user.is_head or lead.assigned_to_id == request.user.id):
            return Response({"detail": "Not your lead."}, status=403)
        data = LeadSerializer(lead).data
        data["bookings"] = [
            {"id": b.id, "status": b.status, "starts_at": b.slot.starts_at.isoformat()}
            for b in sorted(lead.bookings.all(), key=lambda b: b.created_at, reverse=True)
        ]
        return Response(data)