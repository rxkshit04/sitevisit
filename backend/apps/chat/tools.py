import json

from django.utils import timezone

from apps.booking import services as booking_services
from apps.booking.models import Slot
from apps.leads.models import Lead
from apps.messaging.models import OutboxMessage
from apps.messaging.services import queue_booking_message

TOOLS = [
    {
        "name": "get_free_slots",
        "description": "List upcoming free site-visit slots for this buyer's project. Call before offering any time.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "book_slot",
        "description": "Book the buyer into one slot returned by get_free_slots. Only after the buyer clearly chooses it.",
        "input_schema": {
            "type": "object",
            "properties": {"slot_id": {"type": "integer"}},
            "required": ["slot_id"],
        },
    },
    {
        "name": "save_buyer_needs",
        "description": "Record what the buyer told you. Include only fields the buyer actually stated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bhk": {"type": "string", "enum": ["2 BHK", "3 BHK"]},
                "budget_max_lakh": {"type": "number"},
                "timeline": {"type": "string"},
                "note": {"type": "string"},
            },
        },
    },
    {
        "name": "request_human",
        "description": "Hand the chat to a named sales executive.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string", "enum": ["buyer_request", "missing_fact", "other"]}},
            "required": ["reason"],
        },
    },
]


def slot_label(slot) -> str:
    return timezone.localtime(slot.starts_at).strftime("%a %d %b, %I:%M %p")


def exec_name(user):
    return (user.get_full_name() or user.username) if user else None


def map_url(project):
    if project.latitude is None or project.longitude is None:
        return ""
    return f"https://www.google.com/maps?q={project.latitude},{project.longitude}"


def booking_payload(booking) -> dict:
    slot = booking.slot
    return {
        "id": booking.id,
        "starts_at": slot.starts_at.isoformat(),
        "label": slot_label(slot),
        "executive": exec_name(slot.executive),
        "project": slot.project.name,
        "address": slot.project.address,
        "map_url": map_url(slot.project),
    }


def slot_payload(slot) -> dict:
    return {
        "id": slot.id,
        "starts_at": slot.starts_at.isoformat(),
        "label": slot_label(slot),
        "executive": exec_name(slot.executive),
    }


def pick_slots(project_id, limit=8, per_day=3):
    """Spread offers over several days and show each clock time once."""
    out, per_day_count, seen = [], {}, set()
    for s in booking_services.free_slots(project_id=project_id)[:150]:
        day = timezone.localtime(s.starts_at).date()
        if s.starts_at in seen or per_day_count.get(day, 0) >= per_day:
            continue
        seen.add(s.starts_at)
        per_day_count[day] = per_day_count.get(day, 0) + 1
        out.append(s)
        if len(out) >= limit:
            break
    return out


class ToolRunner:
    """Executes the model's tool calls. Booking goes through the same service the API uses."""

    def __init__(self, lead, conversation):
        self.lead = lead
        self.conv = conversation
        self.outputs = []  # raw tool results: part of the text replies may quote numbers from
        self.slots_offered = []
        self.booking = None
        self.handoff_reason = None

    def run(self, name, args) -> str:
        handlers = {
            "get_free_slots": self._slots,
            "book_slot": self._book,
            "save_buyer_needs": self._needs,
            "request_human": self._human,
        }
        handler = handlers.get(name)
        if handler is None:
            out = {"error": "Unknown tool."}
        else:
            try:
                out = handler(args if isinstance(args, dict) else {})
            except (TypeError, ValueError, KeyError):
                out = {"error": "Invalid arguments."}
        text = json.dumps(out, ensure_ascii=False)
        self.outputs.append(text)
        return text

    def _slots(self, args):
        slots = pick_slots(self.lead.project_id)
        self.slots_offered = [slot_payload(s) for s in slots]
        if not slots:
            return {"slots": [], "note": "No free slots right now. Offer a callback from the team."}
        return {"slots": [{"slot_id": s["id"], "when": s["label"], "with": s["executive"]} for s in self.slots_offered]}

    def _book(self, args):
        try:
            slot_id = int(args.get("slot_id"))
        except (TypeError, ValueError):
            return {"error": "slot_id must be a number."}
        # A slot from another project, or one the model made up, is simply "not available".
        slot = (
            Slot.objects.select_related("executive", "project")
            .filter(pk=slot_id, project_id=self.lead.project_id)
            .first()
        )
        if slot is None:
            return {"error": "That slot is not available. Call get_free_slots for current options."}
        try:
            booking = booking_services.book_slot(lead_id=self.lead.id, slot_id=slot.id)
        except booking_services.BookingError as exc:
            return {"error": str(exc)}
        queue_booking_message(booking, OutboxMessage.Kind.CONFIRMATION)
        self.booking = booking
        return {"booked": True, "when": slot_label(slot), "with": exec_name(slot.executive), "project": slot.project.name}

    def _needs(self, args):
        needs = dict(self.conv.needs or {})
        if args.get("bhk") in ("2 BHK", "3 BHK"):
            needs["bhk"] = args["bhk"]
            Lead.objects.filter(pk=self.lead.pk).update(wants=args["bhk"])
        budget = args.get("budget_max_lakh")
        if isinstance(budget, (int, float)) and not isinstance(budget, bool) and 0 < budget < 10000:
            needs["budget_max_lakh"] = budget
        for key in ("timeline", "note"):
            v = args.get(key)
            if isinstance(v, str) and v.strip():
                needs[key] = v.strip()[:200]
        self.conv.needs = needs
        self.conv.save(update_fields=["needs", "updated_at"])
        return {"saved": True}

    def _human(self, args):
        self.handoff_reason = str(args.get("reason") or "other")[:60]
        return {"ok": True, "note": "A sales executive will be assigned."}