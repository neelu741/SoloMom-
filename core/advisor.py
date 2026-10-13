"""
core/advisor.py
Turns flags from rules_engine into one warm, short recommendation.
"""

import json
import re
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List

try:
    from core import budget, database as db, rules_engine
except ImportError:
    import budget
    import database as db
    import rules_engine

LLMFn = Callable[[str, str], str]

PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "advisor_prompt.txt"

DEFAULT_SYSTEM_PROMPT = """\
You are SoloMom Advisor: an indispensable, warm, highly proactive personal executive assistant to a single mother (think of her as your chief / boss, whom you respect deeply and whose family and schedule you manage with precision).

You receive JSON with facts that the app has already calculated.

Rules:
1. Tone: Like an experienced, trustworthy executive assistant briefing their boss in morning standup: respectful, warm, crisp, proactive, and clear ("Good morning Aarti, here is your executive briefing for today:").
2. Format: Return a structured briefing with:
   - "greeting": A warm 1-sentence opening greeting addressing her directly.
   - "headline": Max 8 words summarizing today's executive focus.
   - "items": An array of distinct action briefing bullet objects:
     [{"category": "Schedule"|"Finance"|"Health"|"Wellbeing"|"General", "title": "...", "detail": "...", "recommendation": "...", "action_id": "..."}]
   - "closing": A reassuring 1-sentence assistant sign-off asking how she would like to proceed.
   - "message": A complete conversational text rendition of the briefing formatted with markdown bullets.
   - "action_ids": Array of selected action ids from allowed_actions (up to 3).
3. Grounding: Use ONLY numbers and facts that appear in the JSON. Never invent, estimate, or calculate new figures.
4. Health Safety: Never diagnose or suggest medicines. Only suggest rest, a checkup, or finding a slot with the family doctor.
5. She decides: Always present proposals for her approval ("Shall I...", "Would you like me to...").
6. Reply with JSON only, no other text.
"""

ACTION_LABELS = {
    "trim_spending": "Trim non-essentials this week",
    "pay_due_item": "Mark it as handled",
    "review_schedule": "Review today's schedule",
    "book_vaccine": "Find a slot with the doctor",
    "lighter_evening": "Plan a lighter evening",
    "log_checkin": "Do today's check-in",
}

GROUNDING_MIN_VALUE = 100


def build_context(flags: Optional[List] = None) -> Dict[str, Any]:
    flags = rules_engine.top_flags() if flags is None else flags
    profile = db.get_profile() or {}
    doctor = db.get_primary_doctor()
    report = budget.build_budget_report()

    allowed = {}
    for flag in flags:
        label = ACTION_LABELS.get(flag.action, flag.action)
        if flag.action == "book_vaccine" and doctor:
            label = f"Find a slot with {doctor['name']}"
        allowed[flag.action] = label

    return {
        "mother_first_name": (profile.get("name") or "there").split()[0],
        "children_first_names": [c["name"].split()[0] for c in db.get_children()],
        "today": db.get_today().isoformat(),
        "days_left_in_month": report["progress"]["days_left"],
        "unallocated_budget": report["unallocated"],
        "flags": [{"code": f.code, "severity": f.severity, "detail": f.detail,
                   "action": f.action} for f in flags],
        "allowed_actions": allowed,
    }


def _system_prompt() -> str:
    try:
        return PROMPT_FILE.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_SYSTEM_PROMPT


def _default_llm() -> Optional[LLMFn]:
    try:
        from core.llm_client import complete
        return complete
    except ImportError:
        return None


def _extract_json(text: str) -> Dict[str, Any]:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object in LLM reply.")
    return json.loads(text[start:end + 1])


def _numbers(text: str) -> set[int]:
    values = set()
    for token in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            values.add(int(round(float(token.replace(",", "")))))
        except ValueError:
            pass
    return values


def _numbers_grounded(message: str, context: Dict[str, Any]) -> bool:
    known = _numbers(json.dumps(context, ensure_ascii=False))
    return all(n in known for n in _numbers(message) if n >= GROUNDING_MIN_VALUE)


def _build_bullet_item(flag: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    code = flag["code"]
    detail = flag["detail"]
    action_id = flag.get("action", "")

    if code == "schedule_clash":
        return {
            "category": "Schedule",
            "icon": "📅",
            "title": "Calendar Conflict Detected",
            "detail": detail,
            "recommendation": "Shall I reshuffle your non-critical work block to keep your child's priority clear?",
            "action_id": action_id or "review_schedule"
        }
    elif code == "budget_pace":
        return {
            "category": "Finance",
            "icon": "💰",
            "title": "Category Spending Alert",
            "detail": detail,
            "recommendation": "Shall I place a temporary freeze on non-essential spending for the next 7 days?",
            "action_id": action_id or "trim_spending"
        }
    elif code == "due_soon":
        return {
            "category": "Bills & Deadlines",
            "icon": "⏰",
            "title": "Upcoming Essential Due Date",
            "detail": detail,
            "recommendation": "The funds are reserved in your plan. Shall I mark this reminder ready for payment?",
            "action_id": action_id or "pay_due_item"
        }
    elif code == "vaccine_overdue":
        doctor = db.get_primary_doctor()
        doc_name = doctor["name"] if doctor else "the family clinic"
        return {
            "category": "Health",
            "icon": "💉",
            "title": "Child Vaccination Pending",
            "detail": detail,
            "recommendation": f"Would you like me to request a clinic appointment slot with {doc_name}?",
            "action_id": action_id or "book_vaccine"
        }
    elif code == "low_sleep":
        return {
            "category": "Wellbeing",
            "icon": "🧘",
            "title": "Fatigue & Sleep Alert",
            "detail": detail,
            "recommendation": "I recommend blocking 20:30 onwards strictly for downtime tonight. Shall I clear your evening tasks?",
            "action_id": action_id or "lighter_evening"
        }
    else:
        return {
            "category": "General",
            "icon": "📌",
            "title": "Action Item",
            "detail": detail,
            "recommendation": "Review and confirm if you would like me to adjust this in your plan.",
            "action_id": action_id or "review_schedule"
        }


def _validate(raw: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Missing message.")
    if not _numbers_grounded(message, context):
        raise ValueError("Message contains a number that is not in the facts.")

    allowed = context["allowed_actions"]
    ids = [a for a in raw.get("action_ids", []) if a in allowed][:3]
    
    # Process items if present from LLM, otherwise generate from flags
    items = raw.get("items")
    if not isinstance(items, list) or not items:
        items = [_build_bullet_item(f, context) for f in context.get("flags", [])[:3]]

    greeting = raw.get("greeting") or f"Good morning, {context['mother_first_name']}."
    closing = raw.get("closing") or "I'm standing by to carry out any adjustments you approve."

    return {
        "headline": str(raw.get("headline") or "Executive Daily Briefing").strip(),
        "greeting": greeting,
        "closing": closing,
        "items": items,
        "message": message.strip(),
        "actions": [{"id": a, "label": allowed[a]} for a in ids],
    }


def fallback_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
    name = context["mother_first_name"]
    flags = context["flags"]
    if not flags:
        greeting = f"Good morning, {name}."
        closing = "Your household schedule and finances are running smoothly. I will keep monitoring in the background."
        return {
            "headline": "All Systems Steady",
            "greeting": greeting,
            "closing": closing,
            "items": [
                {
                    "category": "Status",
                    "icon": "✅",
                    "title": "Household in Balance",
                    "detail": "No calendar conflicts, overspending, or overdue medical tasks detected today.",
                    "recommendation": "No urgent actions needed today. Keep moving forward smoothly.",
                    "action_id": "review_schedule"
                }
            ],
            "message": f"{greeting} Everything looks steady today across your finances, health, and schedule. {closing}",
            "actions": []
        }

    items = [_build_bullet_item(f, context) for f in flags[:3]]
    greeting = f"Good morning, {name}. Here is your executive briefing for today:"
    closing = "Please let me know which adjustment you'd like me to execute, and I will update your plan immediately."
    
    # Format conversational message with clear bullet points
    bullet_lines = []
    for it in items:
        bullet_lines.append(f"• [{it['category']}] {it['title']}: {it['detail']} -> Recommendation: {it['recommendation']}")

    message = f"{greeting}\n\n" + "\n\n".join(bullet_lines) + f"\n\n{closing}"
    ids = list(dict.fromkeys(f["action"] for f in flags))[:3]
    allowed = context["allowed_actions"]
    return {
        "headline": "Executive Action Briefing",
        "greeting": greeting,
        "closing": closing,
        "items": items,
        "message": message,
        "actions": [{"id": a, "label": allowed.get(a, a)} for a in ids],
    }


def daily_card(llm: Optional[LLMFn] = None, use_llm: bool = True) -> Dict[str, Any]:
    flags = rules_engine.top_flags()
    context = build_context(flags)
    card, source, error = None, "fallback", None

    llm = llm or (_default_llm() if use_llm else None)
    if flags and use_llm and llm is not None:
        try:
            reply = llm(_system_prompt(),
                        "Facts from the app (JSON):\n" + json.dumps(context, ensure_ascii=False, indent=2))
            card, source = _validate(_extract_json(reply), context), "llm"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
    elif flags and use_llm:
        error = "No LLM configured (using deterministic advisor)."

    if card is None:
        card = fallback_recommendation(context)
    card.update({"flags": [f.to_dict() for f in flags], "source": source, "error": error})
    return card
