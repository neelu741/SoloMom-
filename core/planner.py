"""
core/planner.py
Schedule planning, task management, conflict detection, and reshuffling.
"""

from datetime import date, timedelta
from typing import Dict, Any, List, Optional

try:
    from core import database as db
except ImportError:
    import database as db


def _minutes(hhmm: str) -> int:
    try:
        parts = hhmm.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0


def get_weekly_schedule(start_date: Optional[date] = None) -> List[Dict[str, Any]]:
    today = start_date or db.get_today()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    end_of_week = start_of_week + timedelta(days=6)         # Sunday
    return db.get_tasks(from_date=start_of_week, to_date=end_of_week)


def check_schedule_conflicts(lookahead_days: int = 2) -> List[Dict[str, Any]]:
    today = db.get_today()
    tasks = db.get_tasks(from_date=today, to_date=today + timedelta(days=lookahead_days))
    active_tasks = [t for t in tasks if t["status"] in ("pending", "requested", "confirmed") and t.get("start_time") and t.get("end_time")]

    by_day: Dict[str, List[dict]] = {}
    for t in active_tasks:
        by_day.setdefault(t["due_date"], []).append(t)

    conflicts = []
    for day, items in by_day.items():
        involved = {}
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                a0, a1 = _minutes(a["start_time"]), _minutes(a["end_time"])
                b0, b1 = _minutes(b["start_time"]), _minutes(b["end_time"])
                if a0 < b1 and b0 < a1:
                    involved[a["id"]] = a
                    involved[b["id"]] = b

        if involved:
            conflicts.append({
                "date": day,
                "tasks": list(involved.values()),
            })
    return conflicts


def reshuffle_schedule_for_doctor(appointment_date: date, start_time: str = "17:30", end_time: str = "18:00") -> Dict[str, Any]:
    """
    Automatically postpones non-essential or conflicting tasks when a doctor appointment is added.
    """
    today_tasks = db.get_tasks(on_date=appointment_date)
    postponed_tasks = []

    app_start = _minutes(start_time)
    app_end = _minutes(end_time)

    for t in today_tasks:
        if t["status"] not in ("pending", "confirmed"):
            continue
        if t.get("start_time") and t.get("end_time"):
            t_start = _minutes(t["start_time"])
            t_end = _minutes(t["end_time"])
            if t_start < app_end and app_start < t_end:
                if not t["is_essential"]:
                    db.update_task(t["id"], status="postponed", note="Postponed for doctor visit")
                    postponed_tasks.append(t["title"])
                elif t["kind"] != "appointment":
                    # Shift non-appointment essential task if possible
                    new_due = appointment_date + timedelta(days=1)
                    db.update_task(t["id"], due_date=new_due, note="Rescheduled to tomorrow for doctor visit")
                    postponed_tasks.append(f"{t['title']} (moved to tomorrow)")

    # Add the doctor appointment task
    doc = db.get_primary_doctor()
    doc_name = doc["name"] if doc else "Pediatrician"
    task_id = db.add_task(
        title=f"Doctor visit: {doc_name}",
        due_date=appointment_date,
        kind="appointment",
        start_time=start_time,
        end_time=end_time,
        priority="high",
        is_essential=True,
        status="requested",
        note="Created via SoloMom Advisor Doctor Triage",
    )

    return {
        "appointment_id": task_id,
        "date": appointment_date.isoformat(),
        "time": f"{start_time}-{end_time}",
        "postponed": postponed_tasks,
    }
