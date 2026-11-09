from django.db import transaction
from django.db.models import Count

from apps.accounts.models import User

from .llm import LLMError
from .models import Handoff
from .prompt import SUMMARY_SYSTEM
from .tools import exec_name


def pick_executive(lead):
    """Keep the lead's owner; otherwise the executive with free capacity on this project
    who currently holds the fewest leads (round-robin in effect)."""
    if lead.assigned_to_id:
        return lead.assigned_to
    ranked = (
        User.objects.filter(role=User.Role.EXECUTIVE, slots__project_id=lead.project_id)
        .annotate(open_leads=Count("leads", distinct=True))
        .order_by("open_leads", "id")
    )
    return ranked.first() or User.objects.filter(role=User.Role.EXECUTIVE).order_by("id").first()


def template_summary(lead, conv) -> str:
    needs = conv.needs or {}
    parts = [f"{lead.name} ({lead.get_language_display()}) asked about {lead.project.name}."]
    if lead.wants:
        parts.append(f"Wants {lead.wants}.")
    if "budget_max_lakh" in needs:
        parts.append(f"Budget up to {needs['budget_max_lakh']} lakh.")
    if needs.get("timeline"):
        parts.append(f"Timing: {needs['timeline']}.")
    last = list(conv.messages.filter(role="buyer").order_by("-id").values_list("content", flat=True)[:3])[::-1]
    if last:
        parts.append("Recent messages: " + " | ".join(m[:120] for m in last))
    return " ".join(parts)


def build_summary(lead, conv, llm) -> str:
    """LLM summary when available, otherwise a plain template. A handoff never waits on the model."""
    if llm is not None:
        transcript = "\n".join(f"{m.role}: {m.content}" for m in conv.messages.order_by("id")[:40])
        try:
            blocks = llm.complete(
                system=SUMMARY_SYSTEM,
                messages=[{"role": "user", "content": transcript or "(no messages)"}],
                max_tokens=300,
            )
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
            if text:
                return text[:1500]
        except LLMError:
            pass
    return template_summary(lead, conv)


def create_handoff(*, lead, conversation, reason, llm=None):
    existing = Handoff.objects.filter(conversation=conversation).order_by("-id").first()
    if existing:
        return existing
    executive = pick_executive(lead)
    summary = build_summary(lead, conversation, llm)
    with transaction.atomic():
        if executive and lead.assigned_to_id is None:
            lead.assigned_to = executive
            lead.save(update_fields=["assigned_to"])
        handoff = Handoff.objects.create(
            lead=lead, conversation=conversation, executive=executive, reason=reason[:60], summary=summary
        )
        conversation.handed_off = True
        conversation.flag(reason)
    return handoff


def handoff_payload(handoff) -> dict:
    return {"executive_name": exec_name(handoff.executive), "reason": handoff.reason}