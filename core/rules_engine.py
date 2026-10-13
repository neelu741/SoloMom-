"""
core/rules_engine.py
Deterministic rule engine for scanning household state and returning flags.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

try:
    from core import budget, database as db
    from core.models import Flag
except ImportError:
    import budget
    import database as db
    from models import Flag

LOW_SLEEP_HOURS = 6.0
LOW_SLEEP_MIN_STREAK = 3
DUE_SOON_DAYS = 3
SCHEDULE_LOOKAHEAD_DAYS = 2
NO_CHECKIN_DAYS = 3

SEVERITY_WEIGHT = {"high": 3, "watch": 2, "info": 1}

CODE_PRIORITY = {
    "schedule_clash": 1,
    "budget_pace": 2,
    "due_soon": 3,
    "vaccine_overdue": 4,
    "low_sleep": 5,
    "no_checkin": 9,
}

ACTIVE_STATUSES = ("pending", "requested", "confirmed")


def check_budget() -> List[Flag]:
    report = budget.build_budget_report()
    days_left = report["progress"]["days_left"]
    flags = []
    for c in report["flagged"]:
        over = c["status"] == "over"
        if over:
            detail = (f"{c['category']} is over plan: {budget.fmt_inr(c['spent'])} spent "
                      f"of {budget.fmt_inr(c['planned'])}.")
        else:
            detail = (f"{c['category']} is at {budget.fmt_inr(c['spent'])} of "
                      f"{budget.fmt_inr(c['planned'])} ({c['pct_used']:.0f}% used) with "
                      f"{days_left} days left; at this pace it would reach about "
                      f"{budget.fmt_inr(c['projected_total'])}.")
        data_dict = {k: c[k] for k in ("category", "planned", "spent", "remaining",
                                      "pct_used", "projected_total", "daily_allowance")}
        data_dict["days_left"] = days_left
        flags.append(Flag(
            code="budget_pace",
            severity="high" if over else "watch",
            title=f"{c['category']} spending is running high",
            detail=detail,
            action="trim_spending",
            impact=c["projected_overrun"],
            data=data_dict,
        ))
    return flags


def check_vaccinations() -> List[Flag]:
    doctor = db.get_primary_doctor()
    flags = []
    for v in db.get_vaccinations():
        if v["days_overdue"] <= 0:
            continue
        flags.append(Flag(
            code="vaccine_overdue",
            severity="high" if v["days_overdue"] >= 30 else "watch",
            title=f"{v['child_name']}'s vaccine dose is overdue",
            detail=(f"{v['child_name']}'s dose ({v['vaccine_name']}) is "
                    f"{v['days_overdue']} days overdue and no visit is booked."),
            action="book_vaccine",
            impact=v["days_overdue"],
            data={"vaccination_id": v["id"], "child_name": v["child_name"],
                  "vaccine_name": v["vaccine_name"], "days_overdue": v["days_overdue"],
                  "doctor_name": doctor["name"] if doctor else None},
        ))
    return flags


def check_sleep() -> List[Flag]:
    logs = db.get_recent_wellbeing(days=7)
    streak, hours = 0, []
    for log in logs:
        if log["sleep_hours"] is None or log["sleep_hours"] >= LOW_SLEEP_HOURS:
            break
        streak += 1
        hours.append(log["sleep_hours"])
    if streak < LOW_SLEEP_MIN_STREAK:
        return []

    low_mood_days = sum(1 for log in logs[:5] if log["mood"] in ("tired", "stressed"))
    avg = round(sum(hours) / len(hours), 1)
    return [Flag(
        code="low_sleep",
        severity="high" if streak >= 5 else "watch",
        title="Sleep has been short lately",
        detail=(f"Logged sleep has been under {LOW_SLEEP_HOURS:.0f} hours for {streak} days "
                f"in a row (about {avg} hours on average)."),
        action="lighter_evening",
        impact=streak,
        data={"streak_days": streak, "avg_hours": avg, "tired_or_stressed_days": low_mood_days},
    )]


def _minutes(hhmm: str) -> int:
    try:
        hours, minutes = hhmm.split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, IndexError):
        return 0


def check_schedule() -> List[Flag]:
    today = db.get_today()
    tasks = [t for t in db.get_tasks(from_date=today,
                                     to_date=today + timedelta(days=SCHEDULE_LOOKAHEAD_DAYS))
             if t["status"] in ACTIVE_STATUSES and t.get("start_time") and t.get("end_time")]

    by_day: Dict[str, List[dict]] = {}
    for t in tasks:
        by_day.setdefault(t["due_date"], []).append(t)

    flags = []
    for day, items in by_day.items():
        involved: Dict[int, dict] = {}
        essential_clash = False
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                a0, a1, b0, b1 = (_minutes(a["start_time"]), _minutes(a["end_time"]),
                                  _minutes(b["start_time"]), _minutes(b["end_time"]))
                if a0 < b1 and b0 < a1:
                    involved[a["id"]], involved[b["id"]] = a, b
                    essential_clash |= bool(a["is_essential"] and b["is_essential"])
        if not involved:
            continue

        ordered = sorted(involved.values(), key=lambda t: t["start_time"])
        listing = "; ".join(f"{t['title']} ({t['start_time']}-{t['end_time']})" for t in ordered)
        flags.append(Flag(
            code="schedule_clash",
            severity="high" if essential_clash else "watch",
            title="Your schedule has a clash",
            detail=f"On {day}, these overlap: {listing}.",
            action="review_schedule",
            impact=len(ordered),
            data={"date": day,
                  "tasks": [{"id": t["id"], "title": t["title"], "start": t["start_time"],
                             "end": t["end_time"], "essential": bool(t["is_essential"])}
                            for t in ordered]},
        ))
    return flags


def check_due_soon() -> List[Flag]:
    today = db.get_today()
    flags = []
    for t in db.get_tasks(status="pending", from_date=today,
                          to_date=today + timedelta(days=DUE_SOON_DAYS)):
        if not t["is_essential"]:
            continue
        days_until = (date.fromisoformat(t["due_date"]) - today).days
        when = "today" if days_until == 0 else "tomorrow" if days_until == 1 else f"in {days_until} days"
        amount = budget.parse_amount(t["title"])
        flags.append(Flag(
            code="due_soon",
            severity="watch" if days_until <= 1 else "info",
            title="An important payment or task is coming up",
            detail=f"{t['title']} is due {when}.",
            action="pay_due_item",
            impact=amount or 0,
            data={"task_id": t["id"], "title": t["title"], "due_date": t["due_date"],
                  "days_until": days_until, "amount": amount},
        ))
    return flags


def check_checkin() -> List[Flag]:
    if db.get_recent_wellbeing(days=NO_CHECKIN_DAYS):
        return []
    return [Flag(
        code="no_checkin", severity="info", title="No check-in for a few days",
        detail=f"Nothing has been logged in the last {NO_CHECKIN_DAYS} days.",
        action="log_checkin", data={"days": NO_CHECKIN_DAYS},
    )]


RULES = (check_schedule, check_budget, check_due_soon, check_vaccinations,
         check_sleep, check_checkin)


def evaluate_all() -> List[Flag]:
    flags = [flag for rule in RULES for flag in rule()]
    return sorted(flags, key=lambda f: (-SEVERITY_WEIGHT[f.severity],
                                        CODE_PRIORITY.get(f.code, 99), -f.impact))


def top_flags(limit: int = 5, per_code: int = 1) -> List[Flag]:
    seen: Dict[str, int] = {}
    chosen = []
    for flag in evaluate_all():
        if seen.get(flag.code, 0) >= per_code:
            continue
        seen[flag.code] = seen.get(flag.code, 0) + 1
        chosen.append(flag)
        if len(chosen) == limit:
            break
    return chosen
