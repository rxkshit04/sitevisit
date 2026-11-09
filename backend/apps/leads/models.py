from django.conf import settings
from django.db import models

from .phone import normalise_phone


class Lead(models.Model):
    class Source(models.TextChoices):
        PORTAL = "portal", "Property portal"
        SOCIAL = "social", "Social media ad"
        WEBSITE = "website", "Website"
        HOARDING = "hoarding", "Hoarding call"

    class Language(models.TextChoices):
        EN = "en", "English"
        HI = "hi", "Hindi"
        GU = "gu", "Gujarati"

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    phone_normalised = models.CharField(max_length=10, db_index=True, editable=False)
    source = models.CharField(max_length=20, choices=Source.choices)
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="leads")
    wants = models.CharField(max_length=10, blank=True)  # "2 BHK" / "3 BHK"
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.EN)

    consent_at = models.DateTimeField(null=True, blank=True)
    opted_out = models.BooleanField(default=False)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="leads"
    )
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    first_response_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.phone_normalised = normalise_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.phone_normalised})"