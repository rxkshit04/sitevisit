from collections import defaultdict
from datetime import timedelta
from statistics import median

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsHead
from apps.booking.models import Booking
from apps.leads.models import Lead

from .models import SourceSpend

UNREACHED_AFTER = timedelta(hours=48)
SOURCE_LABELS = dict(Lead.Source.choices)


def _stats(leads, visits_by_lead, spend, now):
    """Metrics for one group of leads. Duplicates are excluded before this is called."""
    responded = [(l.first_response_at - l.created_at).total_seconds() / 60 for l in leads if l.first_response_at]
    old = [l for l in leads if now - l.created_at >= UNREACHED_AFTER]
    unreached = [
        l for l in old if l.first_response_at is None or l.first_response_at - l.created_at > UNREACHED_AFTER
    ]
    visited = sum(visits_by_lead[l.id]["visited"] for l in leads)
    no_show = sum(visits_by_lead[l.id]["no_show"] for l in leads)
    booked = sum(1 for l in leads if visits_by_lead[l.id]["booked"])
    leads_visited = sum(1 for l in leads if visits_by_lead[l.id]["visited"])
    n = len(leads)
    return {
        "leads": n,
        "median_response_min": round(median(responded), 1) if responded else None,
        "not_reached_48h_pct": round(100 * len(unreached) / len(old), 1) if old else None,
        "booked": booked,
        "visited": visited,
        "no_show": no_show,
        "show_up_rate_pct": round(100 * visited / (visited + no_show), 1) if (visited + no_show) else None,
        "lead_to_visit_pct": round(100 * leads_visited / n, 1) if n else None,
        "spend_inr": spend,
        "cost_per_visit_inr": round(spend / visited) if visited and spend else None,
    }


def build_dashboard(days, now=None):
    now = now or timezone.now()
    since = now - timedelta(days=days)
    leads = list(Lead.objects.filter(created_at__gte=since, duplicate_of__isnull=True))

    visits = defaultdict(lambda: {"booked": False, "visited": 0, "no_show": 0})
    rows = Booking.objects.filter(lead_id__in=[l.id for l in leads]).values_list("lead_id", "status")
    for lead_id, status in rows:
        if status != Booking.Status.CANCELLED:
            visits[lead_id]["booked"] = True
        if status == Booking.Status.VISITED:
            visits[lead_id]["visited"] += 1
        elif status == Booking.Status.NO_SHOW:
            visits[lead_id]["no_show"] += 1

    spend = defaultdict(int)
    month_start = timezone.localtime(since).date().replace(day=1)
    for source, amount in SourceSpend.objects.filter(month__gte=month_start).values_list("source", "amount_inr"):
        spend[source] += amount

    by_source = []
    for source in Lead.Source.values:
        group = [l for l in leads if l.source == source]
        row = _stats(group, visits, spend[source], now)
        row.update(source=source, label=SOURCE_LABELS[source])
        by_source.append(row)
    return {"days": days, "overall": _stats(leads, visits, sum(spend.values()), now), "by_source": by_source}


class DashboardView(APIView):
    permission_classes = [IsHead]

    def get(self, request):
        raw = request.query_params.get("days", "30")
        days = int(raw) if raw.isdigit() and 1 <= int(raw) <= 365 else 30
        return Response(build_dashboard(days))