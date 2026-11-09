import logging

from django.utils import timezone

from apps.leads.models import Lead

from . import guards
from .handoff import create_handoff, handoff_payload
from .llm import LLMError, get_client
from .models import ChatMessage, Conversation, FactEntry
from .prompt import build_system
from .texts import HANDOFF_NAMED, HANDOFF_TEAM, HOLDING, OPT_OUT_ACK, SAFE_FALLBACK, t
from .tools import TOOLS, ToolRunner, booking_payload, exec_name

log = logging.getLogger(__name__)

MAX_LEN = 1000
MAX_STEPS = 4
HISTORY = 20


def _client(llm):
    if llm is not None:
        return llm
    try:
        return get_client()
    except LLMError as exc:
        log.warning("LLM unavailable: %s", exc)
        return None


def save_assistant(conv, text, cited=None):
    ChatMessage.objects.create(
        conversation=conv, role=ChatMessage.Role.ASSISTANT, content=text, cited=cited or []
    )
    Lead.objects.filter(pk=conv.lead_id, first_response_at__isnull=True).update(first_response_at=timezone.now())


def _result(reply, runner=None, handoff=None):
    booking = runner.booking if runner and runner.booking else None
    return {
        "reply": reply,
        "slots": [] if booking or not runner else runner.slots_offered,
        "booking": booking_payload(booking) if booking else None,
        "handoff": handoff_payload(handoff) if handoff else None,
    }


def hand_to_person(lead, conv, reason, *, llm=None, summarise=True, reply=None):
    client = _client(llm) if summarise else None
    handoff = create_handoff(lead=lead, conversation=conv, reason=reason, llm=client)
    if reply is None:
        name = exec_name(handoff.executive)
        reply = t(HANDOFF_NAMED, lead.language).format(name=name) if name else t(HANDOFF_TEAM, lead.language)
    return handoff, reply


def request_person(lead, *, llm=None):
    """The always-visible 'talk to a person' button."""
    conv, _ = Conversation.objects.get_or_create(lead=lead)
    ChatMessage.objects.create(conversation=conv, role=ChatMessage.Role.BUYER, content="I'd like to talk to a person.")
    handoff, reply = hand_to_person(lead, conv, "buyer_request", llm=llm)
    save_assistant(conv, reply)
    return _result(reply, handoff=handoff)


def _history(conv):
    rows = list(conv.messages.order_by("-id")[:HISTORY])[::-1]
    out = []
    for m in rows:
        role = "user" if m.role == ChatMessage.Role.BUYER else "assistant"
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n" + m.content
        else:
            out.append({"role": role, "content": m.content})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def _run_loop(client, system, history, runner):
    messages = list(history)
    for _ in range(MAX_STEPS):
        blocks = client.complete(system=system, messages=messages, tools=TOOLS)
        calls = [b for b in blocks if b.get("type") == "tool_use"]
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        if not calls:
            return text
        messages.append({"role": "assistant", "content": blocks})
        results = [
            {"type": "tool_result", "tool_use_id": c["id"], "content": runner.run(c["name"], c.get("input"))}
            for c in calls
        ]
        messages.append({"role": "user", "content": results})
    raise LLMError("The model did not finish after several tool calls.")


def handle_buyer_message(lead, text, *, llm=None):
    """One buyer turn. Returns {reply, slots, booking, handoff}. Never raises for model problems."""
    conv, _ = Conversation.objects.get_or_create(lead=lead)
    text = (text or "").strip()[:MAX_LEN]
    ChatMessage.objects.create(conversation=conv, role=ChatMessage.Role.BUYER, content=text)
    lang = lead.language

    if guards.PRICE_ASK.search(text):
        conv.flag("price_request")

    if guards.is_opt_out(text):
        Lead.objects.filter(pk=lead.pk).update(opted_out=True)
        reply = t(OPT_OUT_ACK, lang)
        save_assistant(conv, reply)
        return _result(reply)

    if guards.asks_for_person(text):
        handoff, reply = hand_to_person(lead, conv, "buyer_request", llm=llm)
        save_assistant(conv, reply)
        return _result(reply, handoff=handoff)

    client = _client(llm)
    if client is None:
        return _hold(lead, conv, "llm_unavailable")

    facts = list(FactEntry.objects.filter(project_id=lead.project_id))
    runner = ToolRunner(lead, conv)
    try:
        raw = _run_loop(client, build_system(lead, conv, facts), _history(conv), runner)
    except LLMError as exc:
        log.warning("LLM failed for lead %s: %s", lead.id, exc)
        return _hold(lead, conv, "llm_error", runner)

    reply, cited = guards.extract_cites(raw)
    problem = None
    if not reply:
        problem = "empty_reply"
    elif not set(cited) <= {f.id for f in facts}:
        problem = "bad_citation"
    else:
        trusted = " ".join(
            [f"{f.title} {f.text}" for f in facts] + runner.outputs + [lead.project.rera_number]
        )
        buyer_text = " ".join(conv.messages.filter(role=ChatMessage.Role.BUYER).values_list("content", flat=True))
        problem = guards.find_violation(reply, trusted, buyer_text)

    if problem:
        log.warning("Reply blocked for lead %s: %s", lead.id, problem)
        handoff, safe = hand_to_person(
            lead, conv, f"guard_{problem}", llm=client, reply=t(SAFE_FALLBACK, lang)
        )
        save_assistant(conv, safe)
        return _result(safe, runner, handoff)

    handoff = None
    if runner.handoff_reason:
        handoff, _ = hand_to_person(lead, conv, runner.handoff_reason, llm=client)
    save_assistant(conv, reply, cited)
    return _result(reply, runner, handoff)


def _hold(lead, conv, reason, runner=None):
    """Model unavailable: fixed holding message, lead queued for a person. The buyer still gets an answer."""
    handoff, reply = hand_to_person(
        lead, conv, reason, summarise=False, reply=t(HOLDING, lead.language)
    )
    save_assistant(conv, reply)
    return _result(reply, runner, handoff)