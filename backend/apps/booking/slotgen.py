from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Slot


def generate_slots(*, project, executive, start_date, days, start_hour=10, end_hour=18):
    """Hourly slots between start_hour and end_hour, IST. Safe to run twice."""
    created = 0
    for d in range(days):
        day = start_date + timedelta(days=d)
        for hour in range(start_hour, end_hour):
            starts = timezone.make_aware(datetime.combine(day, time(hour)))
            _, was_created = Slot.objects.get_or_create(
                executive=executive,
                starts_at=starts,
                defaults={"project": project, "ends_at": starts + timedelta(hours=1)},
            )
            created += int(was_created)
    return created