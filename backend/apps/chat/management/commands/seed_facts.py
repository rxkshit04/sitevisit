from django.core.management.base import BaseCommand

from apps.chat.models import FactEntry
from apps.projects.models import Project


class Command(BaseCommand):
    help = "Add illustrative fact-sheet entries to projects that have none. Run after seed_demo."

    def handle(self, *args, **options):
        added = 0
        for p in Project.objects.all():
            if p.facts.exists():
                continue
            entries = [
                ("Apartment types", f"{p.name} offers 2 BHK and 3 BHK apartments.", True),
                (
                    "Indicative price range",
                    "Apartments across our projects range from ₹65 lakh to ₹1.2 crore depending on size and floor. "
                    "Final pricing is confirmed by the sales team.",
                    True,
                ),
                ("Location", f"{p.name} is at {p.address}.", True),
                ("RERA registration", f"RERA registration number: {p.rera_number}.", True),
                (
                    "Site visits",
                    "Site visits run daily from 10:00 AM to 6:00 PM. Each visit is one hour with a sales executive.",
                    False,
                ),
            ]
            for title, text, registered in entries:
                FactEntry.objects.create(project=p, title=title, text=text, is_registered=registered)
                added += 1
        self.stdout.write(self.style.SUCCESS(f"Added {added} fact entries."))