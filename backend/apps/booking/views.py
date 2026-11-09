from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import free_slots


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return Response({"status": "ok"})


class FreeSlotsView(APIView):
    """Public: the buyer chat and booking page read this."""

    permission_classes = [AllowAny]

    def get(self, request, project_id):
        slots = free_slots(project_id=project_id)[:40]
        return Response(
            [{"id": s.id, "starts_at": s.starts_at.isoformat(), "ends_at": s.ends_at.isoformat()} for s in slots]
        )