from django.conf import settings
from django.db import models


class FactEntry(models.Model):
    """One line of the sales head's fact sheet. The assistant may only state these."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="facts")
    title = models.CharField(max_length=120)
    text = models.TextField()
    is_registered = models.BooleanField(default=True, help_text="Detail from the RERA registration")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project_id", "id"]

    def __str__(self):
        return f"F{self.pk} {self.title}"


class Conversation(models.Model):
    lead = models.OneToOneField("leads.Lead", on_delete=models.CASCADE, related_name="conversation")
    needs = models.JSONField(default=dict, blank=True)
    handed_off = models.BooleanField(default=False)
    flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=60, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def flag(self, reason: str):
        """Mark for the sales head's daily review. The first reason is kept."""
        if not self.flagged:
            self.flagged = True
            self.flag_reason = reason[:60]
        self.reviewed_at = None
        self.save()


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        BUYER = "buyer", "Buyer"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    cited = models.JSONField(default=list, blank=True)  # fact ids the reply claimed to use
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class Handoff(models.Model):
    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="handoffs")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="handoffs")
    executive = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="handoffs"
    )
    reason = models.CharField(max_length=60)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)