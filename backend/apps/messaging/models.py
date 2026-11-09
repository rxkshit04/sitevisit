from django.db import models
from django.db.models import Q


class OutboxMessage(models.Model):
    """Mock WhatsApp/SMS outbox. A real provider would read from here."""

    class Kind(models.TextChoices):
        WELCOME = "welcome", "Welcome"
        CONFIRMATION = "confirmation", "Booking confirmation"
        REMINDER_1D = "reminder_1d", "Reminder, 1 day before"
        REMINDER_2H = "reminder_2h", "Reminder, 2 hours before"

    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="messages_out")
    booking = models.ForeignKey(
        "booking.Booking", null=True, blank=True, on_delete=models.CASCADE, related_name="messages_out"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    channel = models.CharField(max_length=20, default="whatsapp")
    body = models.TextField()
    template_approved = models.BooleanField(default=True)  # mocked opt-in template flag
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "kind"],
                condition=Q(booking__isnull=False),
                name="one_msg_per_booking_kind",
            )
        ]