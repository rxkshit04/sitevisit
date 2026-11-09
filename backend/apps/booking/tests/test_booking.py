import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import IntegrityError, connection, transaction

from apps.booking.models import Booking
from apps.booking.services import (
    AlreadyBooked,
    NothingToChange,
    SlotInPast,
    SlotTaken,
    book_slot,
    cancel_booking,
    free_slots,
    reschedule_booking,
)


def _race(fn, args_list):
    barrier = threading.Barrier(len(args_list))

    def run(args):
        try:
            barrier.wait()
            fn(*args)
            return "won"
        except (SlotTaken, AlreadyBooked) as exc:
            return type(exc).__name__
        finally:
            connection.close()

    with ThreadPoolExecutor(len(args_list)) as pool:
        return list(pool.map(run, args_list))


@pytest.mark.django_db(transaction=True)
def test_ten_buyers_race_for_one_slot_exactly_one_wins(make_lead, make_slot):
    slot = make_slot()
    leads = [make_lead() for _ in range(10)]
    results = _race(lambda lid, sid: book_slot(lead_id=lid, slot_id=sid), [(l.id, slot.id) for l in leads])
    assert results.count("won") == 1
    assert results.count("SlotTaken") == 9
    assert Booking.objects.filter(slot=slot).count() == 1


@pytest.mark.django_db(transaction=True)
def test_same_lead_cannot_book_two_slots_at_once(make_lead, make_slot):
    lead = make_lead()
    slots = [make_slot() for _ in range(5)]
    results = _race(lambda lid, sid: book_slot(lead_id=lid, slot_id=sid), [(lead.id, s.id) for s in slots])
    assert results.count("won") == 1
    assert Booking.objects.filter(lead=lead, status="confirmed").count() == 1


@pytest.mark.django_db
def test_past_slot_rejected(make_lead, make_slot):
    slot = make_slot(hours_from_now=-2)
    with pytest.raises(SlotInPast):
        book_slot(lead_id=make_lead().id, slot_id=slot.id)


@pytest.mark.django_db
def test_booked_slot_leaves_free_list(project, make_lead, make_slot):
    slot = make_slot()
    other = make_slot()
    book_slot(lead_id=make_lead().id, slot_id=slot.id)
    ids = {s.id for s in free_slots(project_id=project.id)}
    assert ids == {other.id}


@pytest.mark.django_db
def test_cancel_frees_slot_and_allows_rebooking(project, make_lead, make_slot):
    slot = make_slot()
    first, second = make_lead(), make_lead()
    b = book_slot(lead_id=first.id, slot_id=slot.id)
    cancel_booking(booking_id=b.id)
    assert slot.id in {s.id for s in free_slots(project_id=project.id)}
    book_slot(lead_id=second.id, slot_id=slot.id)


@pytest.mark.django_db
def test_cancel_twice_fails(make_lead, make_slot):
    b = book_slot(lead_id=make_lead().id, slot_id=make_slot().id)
    cancel_booking(booking_id=b.id)
    with pytest.raises(NothingToChange):
        cancel_booking(booking_id=b.id)


@pytest.mark.django_db
def test_reschedule_frees_old_slot(project, make_lead, make_slot):
    lead = make_lead()
    old_slot, new_slot = make_slot(), make_slot()
    book_slot(lead_id=lead.id, slot_id=old_slot.id)
    new = reschedule_booking(lead_id=lead.id, new_slot_id=new_slot.id)
    assert new.slot_id == new_slot.id
    assert old_slot.id in {s.id for s in free_slots(project_id=project.id)}
    assert Booking.objects.filter(lead=lead, status="confirmed").count() == 1


@pytest.mark.django_db
def test_failed_reschedule_keeps_old_booking(make_lead, make_slot):
    lead, other = make_lead(), make_lead()
    mine, taken = make_slot(), make_slot()
    book_slot(lead_id=lead.id, slot_id=mine.id)
    book_slot(lead_id=other.id, slot_id=taken.id)
    with pytest.raises(SlotTaken):
        reschedule_booking(lead_id=lead.id, new_slot_id=taken.id)
    assert Booking.objects.filter(lead=lead, slot=mine, status="confirmed").exists()


@pytest.mark.django_db
def test_reschedule_without_booking_fails(make_lead, make_slot):
    with pytest.raises(NothingToChange):
        reschedule_booking(lead_id=make_lead().id, new_slot_id=make_slot().id)


@pytest.mark.django_db
def test_database_rejects_double_booking_even_if_service_is_bypassed(make_lead, make_slot):
    slot = make_slot()
    Booking.objects.create(lead=make_lead(), slot=slot)
    with pytest.raises(IntegrityError), transaction.atomic():
        Booking.objects.create(lead=make_lead(), slot=slot)