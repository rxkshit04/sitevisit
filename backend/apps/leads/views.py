import csv
import io

from django.db.models import Prefetch, Q
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffRole
from apps.booking.models import Booking
from apps.messaging.services import queue_welcome
from apps.projects.models import Project

from .models import Lead
from .serializers import LeadSerializer, PublicIntakeSerializer, StaffLeadSerializer
from .services import create_lead
from .tokens import make_lead_token

MAX_CSV_BYTES = 1_000_000
MAX_CSV_ROWS = 500


class PublicIntakeView(APIView):
    """The buyer's first step on the website chat: name, phone, consent."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_intake"

    def post(self, request):
        s = PublicIntakeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        lead, _ = create_lead(
            name=d["name"], phone=d["phone"], source=Lead.Source.WEBSITE,
            project=d["project"], wants=d["wants"], language=d["language"], consent=True,
        )
        queue_welcome(lead)
        # Deliberately not telling the buyer whether the phone was already known.
        return Response({"lead_id": lead.id, "token": make_lead_token(lead.id)}, status=status.HTTP_201_CREATED)


class LeadListCreateView(APIView):
    permission_classes = [IsStaffRole]

    def get(self, request):
        qs = Lead.objects.select_related("project", "assigned_to").prefetch_related(
            Prefetch("bookings", queryset=Booking.objects.select_related("slot"))
        )
        if not request.user.is_head:
            qs = qs.filter(assigned_to=request.user)
        p = request.query_params
        if p.get("source") in Lead.Source.values:
            qs = qs.filter(source=p["source"])
        if p.get("duplicates") == "1":
            qs = qs.filter(duplicate_of__isnull=False)
        if p.get("unassigned") == "1":
            qs = qs.filter(assigned_to__isnull=True)
        q = p.get("q", "").strip()[:50]
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(phone_normalised__icontains=q))
        qs = qs.order_by("-created_at")
        return Response({"count": qs.count(), "results": LeadSerializer(qs[:200], many=True).data})

    def post(self, request):
        s = StaffLeadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        lead, is_dup = create_lead(
            name=d["name"], phone=d["phone"], source=d["source"], project=d["project"],
            wants=d["wants"], language=d["language"], consent=d["consent"],
            assigned_to=None if request.user.is_head else request.user,
        )
        queue_welcome(lead)
        return Response({"lead": LeadSerializer(lead).data, "duplicate": is_dup}, status=status.HTTP_201_CREATED)


class ImportLeadsView(APIView):
    """CSV columns: name, phone, source, project (name), optional wants, language."""

    permission_classes = [IsStaffRole]
    parser_classes = [MultiPartParser]

    def post(self, request):
        f = request.FILES.get("file")
        if f is None:
            return Response({"detail": "Attach a CSV file."}, status=400)
        if f.size > MAX_CSV_BYTES:
            return Response({"detail": "File is too large (limit 1 MB)."}, status=400)
        try:
            text = f.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response({"detail": "File must be UTF-8 text."}, status=400)

        reader = csv.DictReader(io.StringIO(text))
        headers = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
        if not {"name", "phone", "source", "project"} <= headers:
            return Response({"detail": "Header must include name, phone, source, project."}, status=400)

        projects = {p.name.lower(): p.id for p in Project.objects.all()}
        created = duplicates = 0
        errors = []
        for i, raw in enumerate(reader, start=2):  # row 1 is the header
            if i - 1 > MAX_CSV_ROWS:
                errors.append({"row": i, "error": f"Stopped after {MAX_CSV_ROWS} rows."})
                break
            row = {
                (k or "").strip().lower(): v.strip()
                for k, v in raw.items()
                if isinstance(v, str) and v.strip() != ""
            }
            row["project"] = projects.get(row.get("project", "").lower())
            s = StaffLeadSerializer(data=row)
            if not s.is_valid():
                msg = "; ".join(f"{k}: {v[0]}" for k, v in s.errors.items())
                errors.append({"row": i, "error": msg})
                continue
            d = s.validated_data
            _, is_dup = create_lead(
                name=d["name"], phone=d["phone"], source=d["source"], project=d["project"],
                wants=d["wants"], language=d["language"], consent=False,
                assigned_to=None if request.user.is_head else request.user,
            )
            created += 1
            duplicates += int(is_dup)
        return Response({"created": created, "duplicates": duplicates, "errors": errors})