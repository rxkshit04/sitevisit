import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.booking.models import Booking
from apps.booking.services import book_slot
from apps.chat import agent
from apps.chat.llm import LLMError
from apps.chat.models import ChatMessage, Conversation, FactEntry, Handoff
from apps.leads.tokens import make_lead_token
from apps.messaging.models import OutboxMessage
from apps.projects.models import Project


def text(t):
    return [{"type": "text", "text": t}]


def call(name, **args):
    return [{"type": "tool_use", "id": f"t_{name}", "name": name, "input": args}]


class FakeLLM:
    """Plays back scripted model turns. Summary calls (no tools) never consume a script."""

    def __init__(self, *scripts):
        self.scripts = list(scripts)
        self.chat_calls = 0

    def complete(self, *, system, messages, tools=None, max_tokens=600):
        if tools is None:
            return text("Test summary.")
        self.chat_calls += 1
        step = self.scripts.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


@pytest.fixture
def lead(make_lead, make_slot):
    make_slot()  # gives the project an executive with free slots
    return make_lead(consent_at=timezone.now())


@pytest.mark.django_db
def test_missing_fact_hands_off_to_a_named_executive(lead, executive):
    llm = FakeLLM(
        call("request_human", reason="missing_fact"),
        text("I don't have the possession date, so a team member will confirm it for you."),
    )
    r = agent.handle_buyer_message(lead, "When is possession?", llm=llm)
    assert r["handoff"]["executive_name"]
    conv = Conversation.objects.get(lead=lead)
    assert conv.handed_off and conv.flagged and conv.flag_reason == "missing_fact"
    lead.refresh_from_db()
    assert lead.assigned_to_id == executive.id
    assert Handoff.objects.get(lead=lead).summary


@pytest.mark.django_db
def test_discount_in_reply_is_blocked_and_handed_off(lead):
    llm = FakeLLM(text("Sure, I can give you a 5% discount if you book today."))
    r = agent.handle_buyer_message(lead, "Can you do a good rate?", llm=llm)
    assert "discount" not in r["reply"].lower()
    assert Handoff.objects.get(lead=lead).reason == "guard_discount_claim"
    assert Conversation.objects.get(lead=lead).flagged


@pytest.mark.django_db
def test_number_not_in_fact_sheet_is_blocked(lead):
    llm = FakeLLM(text("Possession is in 2029."))
    r = agent.handle_buyer_message(lead, "When do I get the keys?", llm=llm)
    assert r["handoff"] is not None
    assert "2029" not in r["reply"]


@pytest.mark.django_db
def test_number_from_fact_sheet_passes_and_citation_is_stored(lead):
    fact = FactEntry.objects.create(
        project=lead.project, title="Price range", text="Apartments range from ₹65 lakh to ₹1.2 crore."
    )
    llm = FakeLLM(text(f"Apartments range from ₹65 lakh to ₹1.2 crore. {{facts: F{fact.id}}}"))
    r = agent.handle_buyer_message(lead, "What is the price range?", llm=llm)
    assert r["handoff"] is None
    assert "{facts" not in r["reply"]
    assert ChatMessage.objects.filter(role="assistant").latest("id").cited == [fact.id]


@pytest.mark.django_db
def test_unknown_citation_is_blocked(lead):
    llm = FakeLLM(text("We have 2 BHK and 3 BHK homes. {facts: F99999}"))
    r = agent.handle_buyer_message(lead, "What do you have?", llm=llm)
    assert r["handoff"] is not None


@pytest.mark.django_db
def test_opt_out_is_honoured_without_calling_the_model(lead):
    llm = FakeLLM()
    agent.handle_buyer_message(lead, "STOP", llm=llm)
    lead.refresh_from_db()
    assert lead.opted_out
    assert llm.chat_calls == 0


@pytest.mark.django_db
def test_asking_for_a_person_hands_off_without_the_model(lead):
    llm = FakeLLM()
    r = agent.handle_buyer_message(lead, "I want to talk to a real person please", llm=llm)
    assert r["handoff"]["executive_name"]
    assert llm.chat_calls == 0


@pytest.mark.django_db
def test_model_failure_gives_holding_message_and_queues_the_lead(lead, executive):
    r = agent.handle_buyer_message(lead, "Tell me about the project", llm=FakeLLM(LLMError("boom")))
    assert "reply shortly" in r["reply"]
    conv = Conversation.objects.get(lead=lead)
    assert conv.flag_reason == "llm_error" and conv.handed_off
    lead.refresh_from_db()
    assert lead.assigned_to_id == executive.id
    assert lead.first_response_at is not None


@pytest.mark.django_db
def test_tool_cannot_book_a_taken_slot(make_lead, make_slot):
    slot = make_slot()
    first = make_lead(consent_at=timezone.now())
    book_slot(lead_id=first.id, slot_id=slot.id)
    second = make_lead(consent_at=timezone.now())
    llm = FakeLLM(
        call("book_slot", slot_id=slot.id),
        text("Sorry, that slot was just taken. Would another time suit you?"),
    )
    r = agent.handle_buyer_message(second, "Book that one", llm=llm)
    assert r["booking"] is None
    assert Booking.objects.filter(slot=slot).count() == 1


@pytest.mark.django_db
def test_tool_rejects_invented_and_other_project_slots(make_lead, make_slot):
    other = Project.objects.create(name="Project 2", rera_number="TEST-RERA-0002")
    foreign = make_slot(project=other)
    lead = make_lead(consent_at=timezone.now())
    llm = FakeLLM(
        call("book_slot", slot_id=foreign.id),
        call("book_slot", slot_id=999999),
        text("I couldn't book that. Shall I show you the available times?"),
    )
    r = agent.handle_buyer_message(lead, "Book it", llm=llm)
    assert r["booking"] is None
    assert not Booking.objects.filter(lead=lead).exists()


@pytest.mark.django_db
def test_booking_through_tool_returns_booking_and_queues_confirmation(make_lead, make_slot):
    slot = make_slot()
    lead = make_lead(consent_at=timezone.now())
    llm = FakeLLM(call("book_slot", slot_id=slot.id), text("You're all set. I've booked your visit."))
    r = agent.handle_buyer_message(lead, "Yes, book that one", llm=llm)
    assert r["booking"]["id"]
    assert OutboxMessage.objects.filter(lead=lead, kind="confirmation").exists()


@pytest.mark.django_db
def test_free_slots_tool_returns_offerable_slots(lead):
    llm = FakeLLM(call("get_free_slots"), text("Here are a few times. Which one suits you?"))
    r = agent.handle_buyer_message(lead, "I'd like to visit", llm=llm)
    assert r["slots"] and r["slots"][0]["id"]


@pytest.mark.django_db
def test_public_chat_rejects_a_bad_token():
    r = APIClient().post("/api/public/chat/", {"token": "nope", "message": "hi"}, format="json")
    assert r.status_code == 404


@pytest.mark.django_db
def test_public_chat_roundtrip_and_history(lead, monkeypatch):
    monkeypatch.setattr(agent, "get_client", lambda: FakeLLM(text("Hello! How can I help?")))
    c = APIClient()
    token = make_lead_token(lead.id)
    r = c.post("/api/public/chat/", {"token": token, "message": "Hi"}, format="json")
    assert r.status_code == 200 and r.json()["reply"].startswith("Hello")
    h = c.get("/api/public/chat/", {"token": token}).json()
    assert [m["role"] for m in h["messages"]] == ["buyer", "assistant"]
    assert h["project"]["rera_number"]


@pytest.mark.django_db
def test_public_book_then_reschedule_then_cancel(lead, make_slot):
    s1, s2 = make_slot(), make_slot()
    c = APIClient()
    token = make_lead_token(lead.id)
    assert c.post("/api/public/chat/book/", {"token": token, "slot_id": s1.id}, format="json").status_code == 200
    assert c.post("/api/public/chat/book/", {"token": token, "slot_id": s2.id}, format="json").status_code == 200
    assert Booking.objects.get(lead=lead, status="confirmed").slot_id == s2.id
    assert c.post("/api/public/chat/cancel/", {"token": token}, format="json").status_code == 200
    assert not Booking.objects.filter(lead=lead, status="confirmed").exists()


@pytest.mark.django_db
def test_executive_cannot_read_someone_elses_chat(lead, executive):
    Conversation.objects.create(lead=lead)
    other = User.objects.create_user("exec2", password="pw-for-tests-1")
    c = APIClient()
    c.force_authenticate(other)
    assert c.get(f"/api/leads/{lead.id}/chat/").status_code == 403
    lead.assigned_to = executive
    lead.save()
    c.force_authenticate(executive)
    assert c.get(f"/api/leads/{lead.id}/chat/").status_code == 200


@pytest.mark.django_db
def test_flagged_list_and_fact_sheet_are_head_only(lead, executive, project):
    c = APIClient()
    c.force_authenticate(executive)
    assert c.get("/api/chats/flagged/").status_code == 403
    assert c.post("/api/facts/", {"project": project.id, "title": "x", "text": "y"}, format="json").status_code == 403
    head = User.objects.create_user("head1", password="pw-for-tests-1", role=User.Role.HEAD)
    c.force_authenticate(head)
    assert c.get("/api/chats/flagged/").status_code == 200
    r = c.post("/api/facts/", {"project": project.id, "title": "Hours", "text": "Open daily."}, format="json")
    assert r.status_code == 201