import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.mark.django_db
def test_me_requires_login():
    assert APIClient().get("/api/auth/me/").status_code in (401, 403)


@pytest.mark.django_db
def test_login_then_me_returns_role():
    User.objects.create_user("head1", password="pw-for-tests-1", role=User.Role.HEAD)
    c = APIClient()
    assert c.post("/api/auth/login/", {"username": "head1", "password": "bad"}).status_code == 400
    assert c.post("/api/auth/login/", {"username": "head1", "password": "pw-for-tests-1"}).status_code == 200
    assert c.get("/api/auth/me/").json()["role"] == "head"