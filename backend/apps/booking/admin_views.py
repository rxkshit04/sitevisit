from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsHead
from apps.projects.models import Project

from .models import Booking, Slot
from .slotgen import generate_slots


class GenerateSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    executive = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.EXECUTIVE))
    start_date = serializers.DateField()
    days = serializers.IntegerField(min_value=1, max_value=31)
    start_hour = serializers.IntegerField(min_value=6, max_value=21, default=10)
    end_hour = serializers.IntegerField(min_value=7, max_value=22, default=18)

    def validate(self, data):
        if data["end_hour"] <= data["start_hour"]:
            raise serializers.ValidationError("End hour must be after start hour.")
        if data["start_date"] < timezone.localdate():
            raise serializers.ValidationError("Start date cannot be in the past.")
        return data


class ExecutivesView(APIView):
    permission_classes = [IsHead]

    def get(self, request):
        users = User.objects.filter(role=User.Role.EXECUTIVE).order_by("first_name", "id")
        return Response([{"id": u.id, "name": u.get_full_name() or u.username} for u in users])


class ProjectsView(APIView):
    permission_classes = [IsHead]

    def get(self, request):
        return Response([{"id": p.id, "name": p.name, "rera_number": p.rera_number} for p in Project.objects.order_by("id")])


class SlotListGenerateView(APIView):
    permission_classes = [IsHead]

    def get(self, request):
        pid = request.query_params.get("project", "")
        live = Booking.objects.filter(slot=OuterRef("pk")).exclude(status=Booking.Status.CANCELLED)
        qs = (
            Slot.objects.filter(starts_at__gte=timezone.now())
            .select_related("executive")
            .annotate(booked=Exists(live))
        )
        if pid.isdigit():
            qs = qs.filter(project_id=int(pid))
        qs = qs.order_by("starts_at", "executive_id")[:400]
        return Response(
            [
                {
                    "id": s.id,
                    "starts_at": s.starts_at.isoformat(),
                    "executive": s.executive.get_full_name() or s.executive.username,
                    "booked": s.booked,
                }
                for s in qs
            ]
        )

    def post(self, request):
        s = GenerateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        created = generate_slots(
            project=d["project"], executive=d["executive"], start_date=d["start_date"],
            days=d["days"], start_hour=d["start_hour"], end_hour=d["end_hour"],
        )
        return Response({"created": created}, status=201)


class SlotDeleteView(APIView):
    permission_classes = [IsHead]

    def delete(self, request, slot_id):
        slot = get_object_or_404(Slot, pk=slot_id)
        if Booking.objects.filter(slot=slot).exclude(status=Booking.Status.CANCELLED).exists():
            return Response({"detail": "This slot has a booking. Cancel the booking first."}, status=409)
        if slot.starts_at <= timezone.now():
            return Response({"detail": "Past slots cannot be removed."}, status=409)
        Booking.objects.filter(slot=slot, status=Booking.Status.CANCELLED).delete()
        slot.delete()
        return Response(status=204)