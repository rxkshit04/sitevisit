from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.leads.models import Lead

from .models import Booking, Slot


class BookingError(Exception):
    """Base class. The message is safe to show to a buyer."""


class SlotNotFound(BookingError):
    pass


class SlotInPast(BookingError):
    pass


class SlotTaken(BookingError):
    pass


class AlreadyBooked(BookingError):
    pass


class NothingToChange(BookingError):
    pass


def free_slots(*, project_id, now=None):
    """Future slots of a project with no live booking."""
    now = now or timezone.now()
    live = Booking.objects.filter(slot=OuterRef("pk")).exclude(status=Booking.Status.CANCELLED)
    return (
        Slot.objects.filter(project_id=project_id, starts_at__gt=now)
        .filter(~Exists(live))
        .select_related("executive")
    )


def _lock_lead(lead_id):
    return Lead.objects.select_for_update().get(pk=lead_id)


def _lock_bookable_slot(slot_id, now):
    try:
        slot = Slot.objects.select_for_update().get(pk=slot_id)
    except Slot.DoesNotExist:
        raise SlotNotFound("That slot does not exist.")
    if slot.starts_at <= now:
        raise SlotInPast("That time has already passed.")
    if Booking.objects.filter(slot=slot).exclude(status=Booking.Status.CANCELLED).exists():
        raise SlotTaken("Sorry, that slot was just taken.")
    return slot


def _insert(lead, slot):
    # The row locks above make a conflict impossible in normal operation.
    # The partial unique indexes are the backstop if anything ever bypasses them.
    try:
        with transaction.atomic():
            return Booking.objects.create(lead=lead, slot=slot)
    except IntegrityError:
        raise SlotTaken("Sorry, that slot was just taken.")


@transaction.atomic
def book_slot(*, lead_id, slot_id, now=None):
    now = now or timezone.now()
    lead = _lock_lead(lead_id)  # serialises requests for the same lead
    if Booking.objects.filter(lead=lead, status=Booking.Status.CONFIRMED).exists():
        raise AlreadyBooked("You already have a visit booked. Reschedule it instead.")
    slot = _lock_bookable_slot(slot_id, now)
    booking = _insert(lead, slot)
    if lead.assigned_to_id is None:
        lead.assigned_to = slot.executive
        lead.save(update_fields=["assigned_to"])
    return booking


@transaction.atomic
def cancel_booking(*, booking_id, now=None):
    now = now or timezone.now()
    try:
        booking = Booking.objects.select_for_update().get(pk=booking_id)
    except Booking.DoesNotExist:
        raise NothingToChange("Booking not found.")
    if booking.status != Booking.Status.CONFIRMED:
        raise NothingToChange("Only an upcoming booking can be cancelled.")
    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = now
    booking.save(update_fields=["status", "cancelled_at"])
    return booking


@transaction.atomic
def reschedule_booking(*, lead_id, new_slot_id, now=None):
    now = now or timezone.now()
    lead = _lock_lead(lead_id)
    old = (
        Booking.objects.select_for_update()
        .filter(lead=lead, status=Booking.Status.CONFIRMED)
        .first()
    )
    if old is None:
        raise NothingToChange("There is no upcoming visit to reschedule.")
    new_slot = _lock_bookable_slot(new_slot_id, now)  # a failure here leaves the old booking untouched
    old.status = Booking.Status.CANCELLED
    old.cancelled_at = now
    old.save(update_fields=["status", "cancelled_at"])
    return _insert(lead, new_slot)