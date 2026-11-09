from datetime import timedelta

import pytest
from django.utils import timezone

from apps.booking.services import book_slot, cancel_booking
from apps.messaging.models import OutboxMessage
from apps.messaging.services import queue_due_reminders


def consenting(make_lead, **kw):
    return make_lead(consent_at=timezone.now(), **kw)


def kinds():
    return sorted(OutboxMessage.objects.values_list("kind", flat=True))


@pytest.mark.django_db
def test_one_day_reminder_only_inside_window(make_lead, make_slot):
    slot = make_slot(hours_from_now=30)
    book_slot(lead_id=consenting(make_lead).id, slot_id=slot.id)
    assert queue_due_reminders(now=slot.starts_at - timedelta(hours=26)) == 0
    assert queue_due_reminders(now=slot.starts_at - timedelta(hours=23)) == 1
    assert kinds() == ["reminder_1d"]


@pytest.mark.django_db
def test_running_twice_does_not_duplicate(make_lead, make_slot):
    slot = make_slot(hours_from_now=30)
    book_slot(lead_id=consenting(make_lead).id, slot_id=slot.id)
    when = slot.starts_at - timedelta(hours=23)
    queue_due_reminders(now=when)
    assert queue_due_reminders(now=when) == 0
    assert OutboxMessage.objects.count() == 1


@pytest.mark.django_db
def test_late_run_sends_only_the_two_hour_reminder(make_lead, make_slot):
    slot = make_slot(hours_from_now=30)
    book_slot(lead_id=consenting(make_lead).id, slot_id=slot.id)
    queue_due_reminders(now=slot.starts_at - timedelta(hours=1, minutes=30))
    assert kinds() == ["reminder_2h"]


@pytest.mark.django_db
def test_booking_made_close_to_visit_skips_one_day_reminder(make_lead, make_slot):
    slot = make_slot(hours_from_now=10)
    book_slot(lead_id=consenting(make_lead).id, slot_id=slot.id)
    assert queue_due_reminders(now=timezone.now()) == 0
    assert queue_due_reminders(now=slot.starts_at - timedelta(hours=1, minutes=30)) == 1
    assert kinds() == ["reminder_2h"]


@pytest.mark.django_db
def test_cancelled_booking_sends_nothing(make_lead, make_slot):
    slot = make_slot(hours_from_now=30)
    b = book_slot(lead_id=consenting(make_lead).id, slot_id=slot.id)
    cancel_booking(booking_id=b.id)
    assert queue_due_reminders(now=slot.starts_at - timedelta(hours=1)) == 0


@pytest.mark.django_db
def test_opted_out_or_no_consent_sends_nothing(make_lead, make_slot):
    s1, s2 = make_slot(hours_from_now=30), make_slot(hours_from_now=30)
    book_slot(lead_id=consenting(make_lead, opted_out=True).id, slot_id=s1.id)
    book_slot(lead_id=make_lead().id, slot_id=s2.id)
    assert queue_due_reminders(now=s1.starts_at - timedelta(hours=1)) == 0


@pytest.mark.django_db
def test_message_carries_rera_number_and_opt_out(make_lead, make_slot, project):
    slot = make_slot(hours_from_now=30)
    book_slot(lead_id=consenting(make_lead).id, slot_id=slot.id)
    queue_due_reminders(now=slot.starts_at - timedelta(hours=1))
    body = OutboxMessage.objects.get().body
    assert project.rera_number in body and "STOP" in body