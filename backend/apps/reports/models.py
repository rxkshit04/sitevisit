from django.db import models

from apps.leads.models import Lead


class SourceSpend(models.Model):
    """Monthly ad/portal spend per lead source. Entered by the sales head."""

    source = models.CharField(max_length=20, choices=Lead.Source.choices)
    month = models.DateField(help_text="First day of the month")
    amount_inr = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "month"], name="uniq_spend_source_month")]