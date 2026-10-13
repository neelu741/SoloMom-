"""
core/rules_engine.py
Deterministic checks that scan the family's data and raise "flags".

A flag is a plain fact ("Groceries is at 80% with 13 days left"), never advice.
advisor.py turns the top flags into one warm recommendation. Because the rules
are ordinary Python, they are easy to test, explain to judges, and they never
hallucinate.

Rules
-----
    schedule_clash   overlapping tasks on the same day
    budget_pace      category over budget or on pace to exceed it
    due_soon         essential all-day items (e.g. fees) due within 3 days
    vaccine_overdue  child's vaccine dose past its due date
    low_sleep        several days in a row of short self-reported sleep
    no_checkin       nothing logged for 3 days (low priority)

Entry point:  evaluate_all() -> list[Flag], most important first.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Optional

import budget
import database as db

LOW_SLEEP_HOURS = 6.0
LOW_SLEEP_MIN_STREAK = 3
DUE_SOON_DAYS = 3
SCHEDULE_LOOKAHEAD_DAYS = 2
NO_CHECKIN_DAYS = 3

SEVERITY_WEIGHT = {"high": 3, "watch": 2, "info": 1}

# Lower number = shown earlier within the same severity.
CODE_PRIORITY = {
    "schedule_clash": 1,
    "budget_pace": 2,
    "due_soon": 3,
    "vaccine_overdue": 4,
    "low_sleep": 5,
    "no_checkin": 9,
}

ACTIVE_STATUSES = ("pending", "requested", "confirmed")


@dataclass
class Flag:
    code: str                 # rule name, see CODE_PRIORITY
    severity: str             # 'high' | 'watch' | 'info'
    title: str                # short headline
    detail: str               # one factual sentence with the real numbers
    action: str               # id of the action button the UI can offer
    impact: float = 0.0       # used only to order flags of the same code
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Individual rules
# --------------------------------------------------------------------------
def check_budget() -> list[Flag]:
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
        flags.append(Flag(
            code="budget_pace",
            severity="high" if over else "watch",
            title=f"{c['category']} spending is running high",
            detail=detail,
            action="trim_spending",
            impact=c["projected_overrun"],
            data={k: c[k] for k in ("category", "planned", "spent", "remaining",
                                    "pct_used", "projected_total", "daily_allowance")}
                 | {"days_left": days_left},
        ))
    return flags


def check_vaccinations() -> list[Flag]:
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


def check_sleep() -> list[Flag]:
    """Counts the current run of low-sleep days, newest first."""
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
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def check_schedule() -> list[Flag]:
    """Finds overlapping tasks (with start and end times) over the next few days."""
    today = db.get_today()
    tasks = [t for t in db.get_tasks(from_date=today,
                                     to_date=today + timedelta(days=SCHEDULE_LOOKAHEAD_DAYS))
             if t["status"] in ACTIVE_STATUSES and t["start_time"] and t["end_time"]]

    by_day: dict[str, list[dict]] = {}
    for t in tasks:
        by_day.setdefault(t["due_date"], []).append(t)

    flags = []
    for day, items in by_day.items():
        involved: dict[int, dict] = {}
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


def check_due_soon() -> list[Flag]:
    """Essential all-day items (no time slot), such as fee payments."""
    today = db.get_today()
    flags = []
    for t in db.get_tasks(status="pending", from_date=today,
                          to_date=today + timedelta(days=DUE_SOON_DAYS)):
        if not t["is_essential"] or t["start_time"]:
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


def check_checkin() -> list[Flag]:
    if db.get_recent_wellbeing(days=NO_CHECKIN_DAYS):
        return []
    return [Flag(
        code="no_checkin", severity="info", title="No check-in for a few days",
        detail=f"Nothing has been logged in the last {NO_CHECKIN_DAYS} days.",
        action="log_checkin", data={"days": NO_CHECKIN_DAYS},
    )]


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
RULES = (check_schedule, check_budget, check_due_soon, check_vaccinations,
         check_sleep, check_checkin)


def evaluate_all() -> list[Flag]:
    """Run every rule. Most important first: severity, then rule priority, then impact."""
    flags = [flag for rule in RULES for flag in rule()]
    return sorted(flags, key=lambda f: (-SEVERITY_WEIGHT[f.severity],
                                        CODE_PRIORITY.get(f.code, 99), -f.impact))


def top_flags(limit: int = 5, per_code: int = 1) -> list[Flag]:
    """
    The flags the advisor should talk about: at most `per_code` per rule, so one
    noisy rule (e.g. three budget categories) cannot crowd out health or schedule.
    """
    seen: dict[str, int] = {}
    chosen = []
    for flag in evaluate_all():
        if seen.get(flag.code, 0) >= per_code:
            continue
        seen[flag.code] = seen.get(flag.code, 0) + 1
        chosen.append(flag)
        if len(chosen) == limit:
            break
    return chosen


if __name__ == "__main__":
    # Run from the project root after:  python core/database.py
    for flag in evaluate_all():
        print(f"[{flag.severity:<5}] {flag.code:<16} {flag.detail}")