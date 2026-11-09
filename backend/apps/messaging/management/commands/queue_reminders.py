from django.core.management.base import BaseCommand

from apps.messaging.services import queue_due_reminders


class Command(BaseCommand):
    help = "Queue 1-day and 2-hour visit reminders that are due. Run every few minutes."

    def handle(self, *args, **options):
        self.stdout.write(f"Queued {queue_due_reminders()} reminder(s).")