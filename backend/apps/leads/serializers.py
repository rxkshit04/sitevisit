from rest_framework import serializers

from apps.projects.models import Project

from .models import Lead
from .phone import normalise_phone

WANTS = ["2 BHK", "3 BHK"]


class PublicIntakeSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=20)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    wants = serializers.ChoiceField(choices=WANTS, required=False, allow_blank=True, default="")
    language = serializers.ChoiceField(choices=Lead.Language.choices, default=Lead.Language.EN)
    consent = serializers.BooleanField()

    def validate_phone(self, value):
        try:
            return normalise_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Consent is needed so we can contact you about your visit.")
        return value


class StaffLeadSerializer(PublicIntakeSerializer):
    """Staff can add leads that came by phone or portal. Consent may be missing,
    in which case the lead is stored but never messaged."""

    source = serializers.ChoiceField(choices=Lead.Source.choices)
    consent = serializers.BooleanField(default=False)

    def validate_consent(self, value):
        return value


class LeadSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    is_duplicate = serializers.SerializerMethodField()
    latest_visit = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "name", "phone", "source", "source_label", "project", "project_name",
            "wants", "language", "consent_at", "opted_out", "assigned_to", "assigned_to_name",
            "duplicate_of", "is_duplicate", "created_at", "first_response_at", "latest_visit",
        ]
        read_only_fields = fields

    def get_assigned_to_name(self, lead):
        u = lead.assigned_to
        return (u.get_full_name() or u.username) if u else None

    def get_is_duplicate(self, lead):
        return lead.duplicate_of_id is not None

    def get_latest_visit(self, lead):
        bookings = list(lead.bookings.all())
        if not bookings:
            return None
        b = max(bookings, key=lambda x: x.created_at)
        return {"booking_id": b.id, "status": b.status, "starts_at": b.slot.starts_at.isoformat()}