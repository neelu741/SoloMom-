"""
core/health.py
Wellbeing logs analysis and child immunization schedule logic.
"""

from datetime import date, timedelta
from typing import Dict, Any, List, Optional

try:
    from core import database as db
except ImportError:
    import database as db


def log_wellbeing(sleep_hours: float, mood: str, note: Optional[str] = None, log_date: Optional[date] = None) -> None:
    target_date = log_date or db.get_today()
    db.upsert_wellbeing(target_date, sleep_hours, mood, note)


def get_wellbeing_summary(days: int = 7) -> Dict[str, Any]:
    logs = db.get_recent_wellbeing(days=days)
    if not logs:
        return {
            "avg_sleep": 0.0,
            "sleep_streak_low": False,
            "low_sleep_days": 0,
            "mood_counts": {},
            "recent_logs": [],
        }

    valid_sleep = [l["sleep_hours"] for l in logs if l["sleep_hours"] is not None]
    avg_sleep = round(sum(valid_sleep) / len(valid_sleep), 1) if valid_sleep else 0.0

    streak = 0
    for l in logs:
        if l["sleep_hours"] is not None and l["sleep_hours"] < 6.0:
            streak += 1
        else:
            break

    mood_counts = {}
    for l in logs:
        m = l.get("mood")
        if m:
            mood_counts[m] = mood_counts.get(m, 0) + 1

    return {
        "avg_sleep": avg_sleep,
        "sleep_streak_low": streak >= 3,
        "low_sleep_days": streak,
        "mood_counts": mood_counts,
        "recent_logs": logs,
    }


def get_vaccine_status() -> List[Dict[str, Any]]:
    return db.get_vaccinations()


def mark_vaccine_complete(vaccination_id: int) -> None:
    db.mark_vaccination_given(vaccination_id)
