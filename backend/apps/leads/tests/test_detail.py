import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_lead_detail_is_limited_to_owner_or_head(make_lead, executive):
    lead = make_lead()
    c = APIClient()
    c.force_authenticate(executive)
    assert c.get(f"/api/leads/{lead.id}/").status_code == 403
    lead.assigned_to = executive
    lead.save()
    r = c.get(f"/api/leads/{lead.id}/")
    assert r.status_code == 200 and r.json()["bookings"] == []


@pytest.mark.django_db
def test_public_project_list_shows_rera_number(project):
    r = APIClient().get("/api/public/projects/")
    assert r.status_code == 200 and r.json()[0]["rera_number"] == "TEST-RERA-0001"