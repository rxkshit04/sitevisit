import os
import random
from collections import Counter
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.booking.models import Booking, Slot
from apps.booking.services import book_slot
from apps.booking.slotgen import generate_slots
from apps.leads.models import Lead
from apps.leads.services import create_lead
from apps.messaging.models import OutboxMessage
from apps.messaging.services import queue_booking_message, queue_welcome
from apps.projects.models import Project
from apps.reports.models import SourceSpend

FIRST = ["Aarav", "Diya", "Kabir", "Isha", "Yash", "Mansi", "Parth", "Riya", "Dhruv", "Tanvi",
         "Jay", "Heer", "Karan", "Pooja", "Smit", "Zara", "Neel", "Bhavna", "Raj", "Sneha"]
LAST = ["Shah", "Patel", "Mehta", "Desai", "Trivedi", "Joshi", "Parikh", "Modi", "Thakkar", "Vyas", "Pandya", "Amin"]
SOURCES = ["portal", "social", "website", "hoarding"]
WEIGHTS = [35, 35, 20, 10]


class Command(BaseCommand):
    help = "Create illustrative demo data. Needs DEMO_PASSWORD. Use --reset to rebuild."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError("Set DEMO_PASSWORD first (used for the demo accounts only).")
        if Project.objects.exists():
            if not reset:
                raise CommandError("Data already exists. Run with --reset to rebuild it.")
            for model in (OutboxMessage, Booking, Slot, Lead, SourceSpend, Project):
                model.objects.all().delete()

        self.rng = random.Random(42)
        self.now = timezone.now()
        self.today = timezone.localdate()

        projects = self.make_projects()
        execs = self.make_users(password, projects)
        for pid, users in execs.items():
            for u in users:
                generate_slots(project=projects[pid], executive=u, start_date=self.today, days=8)

        self.sample_leads(projects, execs)
        leads = self.random_leads(projects, execs)
        self.duplicates(leads)
        self.spend()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Lead.objects.count()} leads, {Booking.objects.count()} bookings, "
            f"{Slot.objects.count()} slots. Logins: head, meera, rohan, anita, vikram."
        ))

    def make_projects(self):
        p1 = Project.objects.create(
            name="Project 1", rera_number="DEMO-RERA-P1-0001",
            address="Demo address, SG Highway, Ahmedabad", latitude="23.030000", longitude="72.507000",
        )
        p2 = Project.objects.create(
            name="Project 2", rera_number="DEMO-RERA-P2-0002",
            address="Demo address, Shela, Ahmedabad", latitude="23.000000", longitude="72.470000",
        )
        return {p1.id: p1, p2.id: p2}

    def _user(self, username, first, last, role, password):
        user, _ = User.objects.get_or_create(
            username=username, defaults={"first_name": first, "last_name": last, "role": role}
        )
        user.role = role
        user.set_password(password)
        user.save()
        return user

    def make_users(self, password, projects):
        self._user("head", "Kiran", "Desai", User.Role.HEAD, password)
        ids = list(projects)
        roster = [("meera", "Meera", "Iyer", ids[0]), ("rohan", "Rohan", "Mehta", ids[0]),
                  ("anita", "Anita", "Parmar", ids[1]), ("vikram", "Vikram", "Joshi", ids[1])]
        execs = {pid: [] for pid in ids}
        for username, first, last, pid in roster:
            execs[pid].append(self._user(username, first, last, User.Role.EXECUTIVE, password))
        return execs

    def _at(self, day, hour):
        return timezone.make_aware(datetime.combine(day, time(hour)))

    def _set_times(self, lead, created, first_response, owner):
        Lead.objects.filter(pk=lead.pk).update(
            created_at=created, first_response_at=first_response, assigned_to=owner
        )
        lead.refresh_from_db()

    def _past_visit(self, lead, executive, project, starts_at, status):
        slot, _ = Slot.objects.get_or_create(
            executive=executive, starts_at=starts_at,
            defaults={"project": project, "ends_at": starts_at + timedelta(hours=1)},
        )
        if Booking.objects.filter(slot=slot).exists():
            return None
        return Booking.objects.create(lead=lead, slot=slot, status=status)

    def sample_leads(self, projects, execs):
        p1, p2 = list(projects.values())
        now, today = self.now, self.today

        hardik, _ = create_lead(name="Hardik Patel", phone="9000010001", source="portal",
                                project=p1, wants="3 BHK", consent=True)
        self._set_times(hardik, now - timedelta(days=3), now - timedelta(days=3) + timedelta(minutes=2), None)
        slot = Slot.objects.filter(project=p1, starts_at=self._at(today + timedelta(days=1), 11)).order_by("id").first()
        booking = book_slot(lead_id=hardik.id, slot_id=slot.id)
        queue_booking_message(booking, OutboxMessage.Kind.CONFIRMATION)
        queue_welcome(hardik)

        nidhi, _ = create_lead(name="Nidhi Shah", phone="9000010002", source="social",
                               project=p2, wants="2 BHK", consent=True)
        self._set_times(nidhi, now - timedelta(days=1), now - timedelta(days=1) + timedelta(minutes=2), execs[p2.id][0])
        queue_welcome(nidhi)

        kavita, _ = create_lead(name="Kavita Joshi", phone="9000010003", source="hoarding",
                                project=p2, wants="2 BHK", consent=True)
        self._set_times(kavita, now - timedelta(days=6), now - timedelta(days=6) + timedelta(minutes=3), execs[p2.id][1])
        self._past_visit(kavita, execs[p2.id][1], p2, self._at(today - timedelta(days=4), 11), Booking.Status.VISITED)

    def random_leads(self, projects, execs):
        rng, now = self.rng, self.now
        used = {"9000010001", "9000010002", "9000010003"}
        out = []
        for _ in range(52):
            phone = f"98{rng.randint(10000000, 99999999)}"
            while phone in used:
                phone = f"98{rng.randint(10000000, 99999999)}"
            used.add(phone)
            project = rng.choice(list(projects.values()))
            created = now - timedelta(days=rng.uniform(0, 21))
            lead, _ = create_lead(
                name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", phone=phone,
                source=rng.choices(SOURCES, weights=WEIGHTS)[0], project=project,
                wants=rng.choice(["2 BHK", "3 BHK"]),
                language=rng.choices(["en", "hi", "gu"], weights=[60, 25, 15])[0], consent=True,
            )
            r = rng.random()
            if r < 0.78:
                first = created + timedelta(minutes=rng.choice([1, 1, 2, 2, 3, 4, 6, 12]))
            elif r < 0.90:
                first = created + timedelta(hours=rng.randint(5, 20))
            else:
                first = None
            if first and first > now:
                first = None
            age_hours = (now - created).total_seconds() / 3600
            owner = rng.choice(execs[project.id]) if (first or age_hours > 48) else None
            self._set_times(lead, created, first, owner)
            queue_welcome(lead)

            if owner and age_hours > 48 and rng.random() < 0.28:
                visit_day = timezone.localtime(created + timedelta(days=rng.randint(1, 4)))
                starts = visit_day.replace(hour=rng.randint(10, 17), minute=0, second=0, microsecond=0)
                if starts < now - timedelta(hours=1):
                    status = rng.choices([Booking.Status.VISITED, Booking.Status.NO_SHOW], weights=[65, 35])[0]
                    self._past_visit(lead, owner, project, starts, status)
            out.append(lead)

        for lead in rng.sample(out, 2):
            Lead.objects.filter(pk=lead.pk).update(opted_out=True)
        return out

    def duplicates(self, leads):
        others = {"portal": "social", "social": "portal", "website": "portal", "hoarding": "website"}
        for lead in self.rng.sample(leads, 4):
            create_lead(name=lead.name, phone=lead.phone, source=others[lead.source],
                        project=lead.project, wants=lead.wants, consent=True)

    def spend(self):
        counts = Counter(
            (l.source, timezone.localtime(l.created_at).date().replace(day=1)) for l in Lead.objects.all()
        )
        for (source, month), n in counts.items():
            SourceSpend.objects.create(source=source, month=month, amount_inr=1000 * n)