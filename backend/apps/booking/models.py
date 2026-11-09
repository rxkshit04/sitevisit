from django.db import models
from django.db.models import Q


class Slot(models.Model):
    executive = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="slots")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="slots")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.UniqueConstraint(fields=["executive", "starts_at"], name="uniq_exec_slot_start"),
            models.CheckConstraint(condition=Q(ends_at__gt=models.F("starts_at")), name="slot_ends_after_start"),
        ]

    def __str__(self):
        return f"{self.executive_id} @ {self.starts_at:%d %b %H:%M}"


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        VISITED = "visited", "Visited"
        NO_SHOW = "no_show", "No-show"

    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="bookings")
    slot = models.ForeignKey(Slot, on_delete=models.PROTECT, related_name="bookings")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # A slot can hold at most one non-cancelled booking.
            models.UniqueConstraint(
                fields=["slot"],
                condition=~Q(status="cancelled"),
                name="one_live_booking_per_slot",
            ),
            # A lead can hold at most one upcoming (confirmed) booking.
            models.UniqueConstraint(
                fields=["lead"],
                condition=Q(status="confirmed"),
                name="one_confirmed_booking_per_lead",
            ),
        ]