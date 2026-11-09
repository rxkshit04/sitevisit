from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.booking.models import Booking
from apps.reports.models import SourceSpend
from apps.reports.views import build_dashboard


def set_times(lead, created, first):
    type(lead).objects.filter(pk=lead.pk).update(created_at=created, first_response_at=first)


@pytest.mark.django_db
def test_metrics_per_source(make_lead, make_slot):
    now = timezone.now()
    a = make_lead(source="portal")
    b = make_lead(source="portal")
    c = make_lead(source="portal")
    set_times(a, now - timedelta(days=5), now - timedelta(days=5) + timedelta(minutes=2))
    set_times(b, now - timedelta(days=5), now - timedelta(days=5) + timedelta(minutes=10))
    set_times(c, now - timedelta(days=5), None)  # never reached
    Booking.objects.create(lead=a, slot=make_slot(hours_from_now=-30), status="visited")
    Booking.objects.create(lead=b, slot=make_slot(hours_from_now=-29), status="no_show")
    SourceSpend.objects.create(source="portal", month=timezone.localdate().replace(day=1), amount_inr=3000)

    row = next(r for r in build_dashboard(30)["by_source"] if r["source"] == "portal")
    assert row["leads"] == 3
    assert row["median_response_min"] == 6.0
    assert row["not_reached_48h_pct"] == 33.3
    assert row["show_up_rate_pct"] == 50.0
    assert row["lead_to_visit_pct"] == 33.3
    assert row["cost_per_visit_inr"] == 3000


@pytest.mark.django_db
def test_duplicates_are_not_counted(make_lead):
    first = make_lead(source="portal")
    make_lead(source="social", duplicate_of=first)
    assert build_dashboard(30)["overall"]["leads"] == 1


@pytest.mark.django_db
def test_dashboard_and_slot_admin_are_head_only(executive):
    c = APIClient()
    c.force_authenticate(executive)
    assert c.get("/api/dashboard/").status_code == 403
    assert c.get("/api/admin/slots/").status_code == 403
    head = User.objects.create_user("head1", password="pw-for-tests-1", role=User.Role.HEAD)
    c.force_authenticate(head)
    assert c.get("/api/dashboard/").status_code == 200


@pytest.mark.django_db
def test_slot_generate_and_delete_rules(project, executive, make_lead, make_slot):
    from apps.booking.services import book_slot

    head = User.objects.create_user("head1", password="pw-for-tests-1", role=User.Role.HEAD)
    c = APIClient()
    c.force_authenticate(head)
    body = {"project": project.id, "executive": executive.id, "start_date": str(timezone.localdate() + timedelta(days=1)), "days": 2}
    assert c.post("/api/admin/slots/", body, format="json").json()["created"] == 16
    assert c.post("/api/admin/slots/", body, format="json").json()["created"] == 0  # safe to repeat
    bad = dict(body, start_date=str(timezone.localdate() - timedelta(days=1)))
    assert c.post("/api/admin/slots/", bad, format="json").status_code == 400

    booked = make_slot()
    book_slot(lead_id=make_lead().id, slot_id=booked.id)
    assert c.delete(f"/api/admin/slots/{booked.id}/").status_code == 409
    free = make_slot()
    assert c.delete(f"/api/admin/slots/{free.id}/").status_code == 204