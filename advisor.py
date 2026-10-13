"""
core/advisor.py
Turns the rules engine's flags into ONE short, warm recommendation.

Flow
----
    rules_engine.top_flags()  ->  build_context()  ->  LLM  ->  validate  ->  card
                                                         \\__ on any problem __/
                                                          deterministic fallback

Safety and reliability
----------------------
* The LLM only sees facts the app already calculated (first names only, no
  phone numbers) and is told never to invent numbers or give medical advice.
* Its answer must be valid JSON, may only choose from the allowed action ids,
  and any rupee-sized number it writes must already exist in the facts.
  If any check fails, the template-based fallback is used instead.
* The fallback also keeps the demo working with no internet or API key.

LLM hook
--------
Pass any function  llm(system_prompt: str, user_prompt: str) -> str,
or create core/llm_client.py with a  complete(system_prompt, user_prompt) -> str
function and it will be picked up automatically.

Entry point:  daily_card(llm=None) -> dict
"""

import json
import re
from pathlib import Path
from typing import Callable, Optional

from core import budget, database as db, rules_engine

LLMFn = Callable[[str, str], str]

PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "advisor_prompt.txt"

DEFAULT_SYSTEM_PROMPT = """\
You are SoloMom Advisor: a warm, practical family advisor for a single mother in \
India. Think of a wise elder in the family, but sharper and never preachy.

You receive JSON with facts that the app has already calculated.

Rules:
1. Use ONLY numbers that appear in the JSON. Never invent, estimate or calculate new figures.
2. Never diagnose, name illnesses, or suggest medicines. For health, you may only \
suggest rest, a checkup, or seeing the doctor.
3. Lead with the single most urgent item. Mention at most two others in one short \
sentence each. Then give ONE clear recommended next step.
4. Under 110 words. Plain, warm English. Address her by first name. No guilt, no lectures.
5. She decides. Phrase suggestions as offers ("Shall I...?").
6. Reply with JSON only, no other text:
   {"headline": "<max 8 words>", "message": "<the advice>", "action_ids": ["<id>", ...]}
   Choose up to 3 ids from allowed_actions, most important first.
"""

ACTION_LABELS = {
    "trim_spending": "Trim non-essentials this week",
    "pay_due_item": "Mark it as handled",
    "review_schedule": "Review today's schedule",
    "book_vaccine": "Find a slot with the doctor",
    "lighter_evening": "Plan a lighter evening",
    "log_checkin": "Do today's check-in",
}

# Rupee-sized numbers (>= this) written by the LLM must exist in the facts.
GROUNDING_MIN_VALUE = 100


# --------------------------------------------------------------------------
# Context (what the LLM is allowed to see)
# --------------------------------------------------------------------------
def build_context(flags: Optional[list] = None) -> dict:
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


# --------------------------------------------------------------------------
# LLM call and validation
# --------------------------------------------------------------------------
def _system_prompt() -> str:
    try:
        return PROMPT_FILE.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_SYSTEM_PROMPT


def _default_llm() -> Optional[LLMFn]:
    try:
        from core.llm_client import complete  # written separately
        return complete
    except ImportError:
        return None


def _extract_json(text: str) -> dict:
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


def _numbers_grounded(message: str, context: dict) -> bool:
    """Every big number in the message must already exist in the facts."""
    known = _numbers(json.dumps(context, ensure_ascii=False))
    return all(n in known for n in _numbers(message) if n >= GROUNDING_MIN_VALUE)


def _validate(raw: dict, context: dict) -> dict:
    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Missing message.")
    if not _numbers_grounded(message, context):
        raise ValueError("Message contains a number that is not in the facts.")

    allowed = context["allowed_actions"]
    ids = [a for a in raw.get("action_ids", []) if a in allowed][:3]
    return {
        "headline": str(raw.get("headline") or "A few things for today").strip(),
        "message": message.strip(),
        "actions": [{"id": a, "label": allowed[a]} for a in ids],
    }


# --------------------------------------------------------------------------
# Deterministic fallback (also the offline demo mode)
# --------------------------------------------------------------------------
def _fallback_line(flag: dict, context: dict) -> str:
    code = flag["code"]
    if code == "schedule_clash":
        return f"Heads up: {flag['detail']} Let's decide what can move."
    if code == "budget_pace":
        return f"{flag['detail']} Let's go easy on non-essentials this week."
    if code == "due_soon":
        return f"{flag['detail']} It's already in your plan, so let's keep that money safe."
    if code == "vaccine_overdue":
        doctor = db.get_primary_doctor()
        offer = f" Shall I find a slot with {doctor['name']}?" if doctor else ""
        return f"{flag['detail']}{offer}"
    if code == "low_sleep":
        return f"{flag['detail']} Let's keep this evening light so you can rest."
    return flag["detail"]


def fallback_recommendation(context: dict) -> dict:
    name = context["mother_first_name"]
    flags = context["flags"]
    if not flags:
        return {"headline": "All on track",
                "message": f"{name}, everything looks steady today. Nothing needs "
                           "changing. Keep going, and tell me if anything shifts.",
                "actions": []}

    lines = [_fallback_line(f, context) for f in flags[:3]]
    message = f"{name}, here is how today looks. " + " ".join(lines) + \
              " You decide what we change; I'll adjust the plan."
    ids = list(dict.fromkeys(f["action"] for f in flags))[:3]
    allowed = context["allowed_actions"]
    return {
        "headline": "A few things need your attention",
        "message": message,
        "actions": [{"id": a, "label": allowed.get(a, a)} for a in ids],
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def daily_card(llm: Optional[LLMFn] = None, use_llm: bool = True) -> dict:
    """
    Build today's advisor card.

    Returns {headline, message, actions[{id,label}], flags[...], source, error}.
    source is 'llm' or 'fallback'; error explains why the fallback was used.
    """
    flags = rules_engine.top_flags()
    context = build_context(flags)
    card, source, error = None, "fallback", None

    llm = llm or (_default_llm() if use_llm else None)
    if flags and use_llm and llm is not None:
        try:
            reply = llm(_system_prompt(),
                        "Facts from the app (JSON):\n" + json.dumps(context, ensure_ascii=False, indent=2))
            card, source = _validate(_extract_json(reply), context), "llm"
        except Exception as exc:  # any LLM, network, parse or validation problem
            error = f"{type(exc).__name__}: {exc}"
    elif flags and use_llm:
        error = "No LLM configured."

    if card is None:
        card = fallback_recommendation(context)
    card.update({"flags": [f.to_dict() for f in flags], "source": source, "error": error})
    return card


if __name__ == "__main__":
    # Run from the project root after:  python core/database.py
    result = daily_card()
    print(f"[{result['source']}] {result['headline']}\n{result['message']}")
    print("Actions:", [a["label"] for a in result["actions"]])
    if result["error"]:
        print("Note:", result["error"])
        