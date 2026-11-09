from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.booking.outcomes import mark_outcome
from apps.booking.services import NothingToChange, book_slot


@pytest.mark.django_db
def test_cannot_mark_before_visit_time(make_lead, make_slot):
    b = book_slot(lead_id=make_lead().id, slot_id=make_slot().id)
    with pytest.raises(NothingToChange):
        mark_outcome(booking_id=b.id, outcome="visited")


@pytest.mark.django_db
def test_mark_visited_and_no_show_after_slot(make_lead, make_slot):
    slot = make_slot()
    b = book_slot(lead_id=make_lead().id, slot_id=slot.id)
    done = mark_outcome(booking_id=b.id, outcome="no_show", now=slot.starts_at + timedelta(hours=2))
    assert done.status == "no_show"
    with pytest.raises(NothingToChange):
        mark_outcome(booking_id=b.id, outcome="visited", now=slot.starts_at + timedelta(hours=2))


@pytest.mark.django_db
def test_invalid_outcome_rejected(make_lead, make_slot):
    b = book_slot(lead_id=make_lead().id, slot_id=make_slot().id)
    with pytest.raises(NothingToChange):
        mark_outcome(booking_id=b.id, outcome="cancelled", now=b.slot.starts_at + timedelta(hours=2))


@pytest.mark.django_db
def test_other_executive_cannot_mark_my_visit(make_lead, make_slot, executive):
    b = book_slot(lead_id=make_lead().id, slot_id=make_slot().id)
    other = User.objects.create_user("exec2", password="pw-for-tests-1")
    c = APIClient()
    c.force_authenticate(other)
    assert c.post(f"/api/bookings/{b.id}/outcome/", {"outcome": "visited"}, format="json").status_code == 403
    c.force_authenticate(executive)
    assert c.post(f"/api/bookings/{b.id}/outcome/", {"outcome": "visited"}, format="json").status_code == 409