from django.conf import settings
from django.utils import timezone

from .models import OutboxMessage

Kind = OutboxMessage.Kind


def _footer(project):
    return f"{project.name} | RERA Reg. No. {project.rera_number}. Reply STOP to opt out."


def _map_link(project):
    if project.latitude is None or project.longitude is None:
        return project.address
    return f"https://www.google.com/maps?q={project.latitude},{project.longitude}"


def welcome(lead):
    first = lead.name.split()[0]
    return (
        f"Hello {first}, thanks for your interest in {lead.project.name}. "
        f"Ask us anything or book a site visit: {settings.PUBLIC_APP_URL}/chat/{lead.project_id}\n"
        f"{_footer(lead.project)}"
    )


def booking_text(booking, kind):
    slot = booking.slot
    project = slot.project
    exec_name = slot.executive.get_full_name() or slot.executive.username
    opener = {
        Kind.CONFIRMATION: "Your site visit is confirmed.",
        Kind.REMINDER_1D: "Reminder: your site visit is tomorrow.",
        Kind.REMINDER_2H: "Reminder: your site visit is in 2 hours.",
    }[kind]
    when = timezone.localtime(slot.starts_at).strftime("%a %d %b, %I:%M %p")
    return (
        f"{opener}\n{when} at {project.name}. You will meet {exec_name}.\n"
        f"Location: {_map_link(project)}\n{_footer(project)}"
    )