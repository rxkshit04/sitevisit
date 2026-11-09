from datetime import timedelta

from django.utils import timezone

from apps.booking.models import Booking
from apps.leads.models import Lead

from . import texts
from .models import OutboxMessage

Kind = OutboxMessage.Kind

# Shortest window first: when a run is late, only the most relevant reminder is sent.
WINDOWS = ((Kind.REMINDER_2H, timedelta(hours=2)), (Kind.REMINDER_1D, timedelta(hours=24)))


def can_contact(lead) -> bool:
    """DPDP: contact only with consent, and never after an opt-out."""
    return lead.consent_at is not None and not lead.opted_out


def _mark_first_response(lead):
    Lead.objects.filter(pk=lead.pk, first_response_at__isnull=True).update(first_response_at=timezone.now())


def queue_welcome(lead):
    if lead.duplicate_of_id or not can_contact(lead):
        return None
    if OutboxMessage.objects.filter(lead=lead, kind=Kind.WELCOME).exists():
        return None
    msg = OutboxMessage.objects.create(lead=lead, kind=Kind.WELCOME, body=texts.welcome(lead))
    _mark_first_response(lead)
    return msg


def queue_booking_message(booking, kind):
    lead = booking.lead
    if not can_contact(lead):
        return None
    msg, created = OutboxMessage.objects.get_or_create(
        booking=booking,
        kind=kind,
        defaults={"lead": lead, "body": texts.booking_text(booking, kind)},
    )
    return msg if created else None


def queue_due_reminders(now=None) -> int:
    """Queue 1-day and 2-hour reminders that are due. Safe to run every few minutes."""
    now = now or timezone.now()
    bookings = Booking.objects.filter(
        status=Booking.Status.CONFIRMED, slot__starts_at__gt=now
    ).select_related("lead", "slot__project", "slot__executive")
    queued = 0
    for booking in bookings:
        for kind, lead_time in WINDOWS:
            send_at = booking.slot.starts_at - lead_time
            if booking.created_at > send_at:
                continue  # booked after this reminder's moment: it would be noise
            if now >= send_at:
                if queue_booking_message(booking, kind) is not None:
                    queued += 1
                break
    return queued