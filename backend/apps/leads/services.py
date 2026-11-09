from django.utils import timezone

from .models import Lead
from .phone import normalise_phone


def create_lead(*, name, phone, source, project, wants="", language="en", consent=False, assigned_to=None):
    """Create a lead. A lead whose normalised phone already exists points at the
    first one (duplicate_of) and inherits its owner. Returns (lead, is_duplicate)."""
    normalised = normalise_phone(phone)
    original = (
        Lead.objects.filter(phone_normalised=normalised, duplicate_of__isnull=True)
        .order_by("created_at")
        .first()
    )
    if assigned_to is None and original is not None:
        assigned_to = original.assigned_to
    lead = Lead.objects.create(
        name=name,
        phone=normalised,
        source=source,
        project=project,
        wants=wants,
        language=language,
        consent_at=timezone.now() if consent else None,
        duplicate_of=original,
        assigned_to=assigned_to,
    )
    return lead, original is not None