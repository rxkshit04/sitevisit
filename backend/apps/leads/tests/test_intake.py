import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.leads.models import Lead

PUBLIC = "/api/public/leads/"


@pytest.fixture(autouse=True)
def _clear_throttle():
    cache.clear()


def payload(project, **kw):
    data = dict(name="Test Buyer", phone="98765 43210", project=project.id, wants="2 BHK", language="en", consent=True)
    data.update(kw)
    return data


@pytest.mark.django_db
def test_public_intake_needs_consent(project):
    r = APIClient().post(PUBLIC, payload(project, consent=False), format="json")
    assert r.status_code == 400
    assert Lead.objects.count() == 0


@pytest.mark.django_db
def test_public_intake_rejects_bad_phone(project):
    r = APIClient().post(PUBLIC, payload(project, phone="12345"), format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_public_intake_creates_lead_welcome_and_token(project):
    r = APIClient().post(PUBLIC, payload(project), format="json")
    assert r.status_code == 201 and "token" in r.json()
    lead = Lead.objects.get()
    assert lead.source == "website" and lead.phone_normalised == "9876543210" and lead.consent_at
    assert lead.messages_out.filter(kind="welcome").count() == 1
    assert lead.first_response_at is not None


@pytest.mark.django_db
def test_same_phone_is_duplicate_and_not_leaked_or_messaged_twice(project):
    c = APIClient()
    c.post(PUBLIC, payload(project), format="json")
    r = c.post(PUBLIC, payload(project, phone="+91 9876543210"), format="json")
    first, second = Lead.objects.order_by("id")
    assert second.duplicate_of_id == first.id
    assert "duplicate" not in r.json()
    assert second.messages_out.count() == 0


@pytest.mark.django_db
def test_public_endpoint_is_rate_limited(project):
    c = APIClient()
    codes = [c.post(PUBLIC, payload(project, phone=f"98000{i:05d}"), format="json").status_code for i in range(22)]
    assert 429 in codes


@pytest.mark.django_db
def test_anonymous_cannot_list_leads():
    assert APIClient().get("/api/leads/").status_code in (401, 403)


@pytest.mark.django_db
def test_executive_sees_only_own_leads_head_sees_all(make_lead, executive):
    other = User.objects.create_user("exec2", password="pw-for-tests-1")
    mine = make_lead(assigned_to=executive)
    make_lead(assigned_to=other)
    make_lead()
    c = APIClient()
    c.force_authenticate(executive)
    assert [x["id"] for x in c.get("/api/leads/").json()["results"]] == [mine.id]
    head = User.objects.create_user("head1", password="pw-for-tests-1", role=User.Role.HEAD)
    c.force_authenticate(head)
    assert c.get("/api/leads/").json()["count"] == 3


@pytest.mark.django_db
def test_csv_import_reports_created_duplicates_and_row_errors(project):
    head = User.objects.create_user("head1", password="pw-for-tests-1", role=User.Role.HEAD)
    text = (
        "name,phone,source,project,wants\n"
        "A One,9811111111,portal,Project 1,2 BHK\n"
        "B Two,12345,portal,Project 1,\n"
        "C Three,9811111111,social,Project 1,3 BHK\n"
    )
    c = APIClient()
    c.force_authenticate(head)
    r = c.post("/api/leads/import/", {"file": SimpleUploadedFile("l.csv", text.encode(), "text/csv")}, format="multipart")
    body = r.json()
    assert body["created"] == 2 and body["duplicates"] == 1
    assert len(body["errors"]) == 1 and body["errors"][0]["row"] == 3
    assert Lead.objects.filter(consent_at__isnull=False).count() == 0