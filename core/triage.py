"""
core/triage.py
Health symptom triage and family doctor booking action flow.
Includes safety red-flag detector to route medical emergencies directly to hospital care.
"""

from datetime import date
from typing import Dict, Any, List, Optional

try:
    from core import budget, database as db, planner
except ImportError:
    import budget
    import database as db
    import planner

RED_FLAG_KEYWORDS = [
    "chest pain", "difficulty breathing", "breathless", "shortness of breath",
    "seizure", "fits", "unconscious", "fainted", "head injury", "bleeding heavily",
    "stiff neck", "high fever with lethargy", "blue lips", "convulsion", "severe allergic"
]


def check_red_flags(symptoms_text: str) -> bool:
    """Returns True if symptoms contain high-risk emergency red flags."""
    text = (symptoms_text or "").lower()
    return any(keyword in text for keyword in RED_FLAG_KEYWORDS)


def triage_symptoms(symptoms_text: str, patient_name: str = "child") -> Dict[str, Any]:
    """
    Evaluates symptoms and returns triage assessment:
    If red flag -> EMERGENCY warning (skip booking).
    If mild/moderate -> Doctor recommendation & simulated booking offer.
    """
    is_emergency = check_red_flags(symptoms_text)
    doc = db.get_primary_doctor()
    doctor_name = doc["name"] if doc else "Pediatrician"

    if is_emergency:
        return {
            "is_emergency": True,
            "headline": "🚨 GO TO A HOSPITAL IMMEDIATELY",
            "recommendation": (
                f"The symptoms you described for {patient_name} suggest a potential medical emergency. "
                "Do NOT wait for a clinic appointment. Please visit the nearest hospital emergency room "
                "or call emergency medical assistance right away."
            ),
            "doctor_action_offered": False,
            "emergency_contacts": [
                {"label": "Emergency Medical (India)", "number": "108"},
                {"label": "Trusted Contact (Sunita)", "number": db.get_profile().get("trusted_contact_phone", "9876543210") if db.get_profile() else "9876543210"},
            ],
        }

    return {
        "is_emergency": False,
        "headline": f"Recommended: Consult {doctor_name}",
        "recommendation": (
            f"Based on what you logged for {patient_name} ({symptoms_text}), it is best to have {doctor_name} examine them. "
            "Keep them hydrated and comfortable. Would you like me to book a clinic consultation slot for today?"
        ),
        "doctor_action_offered": True,
        "doctor_name": doctor_name,
        "clinic_hours": doc.get("clinic_hours", "10:00-13:00, 17:00-20:00") if doc else "17:00-20:00",
        "estimated_fee": 500,
    }


def execute_doctor_booking(appointment_date: Optional[date] = None, slot_time: str = "17:30") -> Dict[str, Any]:
    """
    Executes simulated doctor booking:
    1. Creates appointment task in tasks database.
    2. Re-shuffles schedule.
    3. Reallocates ₹500 for consultation fee.
    """
    app_date = appointment_date or db.get_today()
    doc = db.get_primary_doctor()
    doc_name = doc["name"] if doc else "Dr. Sharma"

    # 1. Budget reallocation
    unplanned = budget.plan_unplanned_expense(500, target_category="Medical Buffer")
    applied = budget.apply_reallocation(unplanned)

    # 2. Schedule reshuffle & appointment task
    reshuffle = planner.reshuffle_schedule_for_doctor(app_date, start_time=slot_time, end_time="18:00")

    return {
        "status": "confirmed",
        "doctor_name": doc_name,
        "date": app_date.isoformat(),
        "time": slot_time,
        "fee": 500,
        "budget_reallocated": True,
        "postponed_tasks": reshuffle["postponed"],
    }
