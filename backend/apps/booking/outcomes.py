from django.db import transaction
from django.utils import timezone

from .models import Booking
from .services import NothingToChange

ALLOWED = {Booking.Status.VISITED, Booking.Status.NO_SHOW}


@transaction.atomic
def mark_outcome(*, booking_id, outcome, now=None):
    now = now or timezone.now()
    if outcome not in ALLOWED:
        raise NothingToChange("Outcome must be visited or no_show.")
    try:
        booking = Booking.objects.select_for_update().select_related("slot").get(pk=booking_id)
    except Booking.DoesNotExist:
        raise NothingToChange("Booking not found.")
    if booking.status != Booking.Status.CONFIRMED:
        raise NothingToChange("Only a confirmed booking can be marked.")
    if booking.slot.starts_at > now:
        raise NothingToChange("The visit has not happened yet.")
    booking.status = outcome
    booking.save(update_fields=["status"])
    return booking