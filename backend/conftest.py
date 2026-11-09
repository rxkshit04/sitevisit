import itertools
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.booking.models import Slot
from apps.leads.models import Lead
from apps.projects.models import Project


@pytest.fixture
def project(db):
    return Project.objects.create(name="Project 1", rera_number="TEST-RERA-0001")


@pytest.fixture
def executive(db):
    return User.objects.create_user("exec1", password="pw-for-tests-1", role=User.Role.EXECUTIVE)


@pytest.fixture
def make_lead(db, project):
    counter = itertools.count(1)

    def _make(**kw):
        n = next(counter)
        data = dict(name=f"Buyer {n}", phone=f"90000{n:05d}", source=Lead.Source.WEBSITE, project=project)
        data.update(kw)
        return Lead.objects.create(**data)

    return _make


@pytest.fixture
def make_slot(db, project, executive):
    counter = itertools.count(1)

    def _make(hours_from_now=24, **kw):
        start = timezone.now() + timedelta(hours=hours_from_now, minutes=next(counter))
        data = dict(executive=executive, project=project, starts_at=start, ends_at=start + timedelta(hours=1))
        data.update(kw)
        return Slot.objects.create(**data)

    return _make