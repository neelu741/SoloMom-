"""
api/routes_dashboard.py
FastAPI router for dashboard summary, today's card, active flags, and profile management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from core import advisor, budget, database as db, rules_engine

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class ProfileUpdateModel(BaseModel):
    name: str
    monthly_income: float
    age: Optional[int] = None
    city: Optional[str] = None
    occupation: Optional[str] = None
    work_start: Optional[str] = "09:00"
    work_end: Optional[str] = "18:00"
    trusted_contact_name: Optional[str] = None
    trusted_contact_phone: Optional[str] = None


@router.get("/card")
def get_daily_card():
    """Returns today's instant executive advisor recommendation card."""
    # Instantly loads preloaded deterministic briefing rules without waiting for external API network latency
    card = advisor.daily_card(use_llm=False)
    return card


@router.get("/summary")
def get_dashboard_summary():
    """Returns monthly budget summary metrics and month progress."""
    report = budget.build_budget_report()
    profile = db.get_profile() or {}
    children = db.get_children()
    doctor = db.get_primary_doctor()
    
    return {
        "active_persona": db.get_active_persona(),
        "profile": profile,
        "children": children,
        "doctor": doctor,
        "today": db.get_today().isoformat(),
        "report": report,
    }


@router.get("/flags")
def get_active_flags():
    """Returns active flags evaluated by rules engine."""
    flags = rules_engine.evaluate_all()
    return [f.to_dict() for f in flags]


@router.get("/tasks")
def get_weekly_tasks():
    """Returns active tasks for the current week."""
    today = db.get_today()
    tasks = db.get_tasks(from_date=today)
    return tasks


class TaskStatusUpdateModel(BaseModel):
    status: str  # 'done' | 'pending' | 'postponed' | 'cancelled'


@router.post("/tasks/{task_id}/status")
def update_task_status(task_id: int, item: TaskStatusUpdateModel):
    """Updates the status of a specific task."""
    stat = "done" if item.status in ("completed", "done") else item.status
    db.update_task(task_id, status=stat)
    return {"status": "success", "task_id": task_id, "new_status": stat}


@router.post("/tasks/{task_id}/toggle-complete")
def toggle_task_complete(task_id: int):
    """Toggles a task between done and pending."""
    tasks = db.get_tasks()
    target = next((t for t in tasks if t["id"] == task_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Task not found")
    
    current_status = target.get("status", "pending")
    new_status = "pending" if current_status in ("done", "completed") else "done"
    db.update_task(task_id, status=new_status)
    return {"status": "success", "task_id": task_id, "previous_status": current_status, "new_status": new_status}


@router.get("/profile")
def get_profile_details():
    profile = db.get_profile() or {}
    children = db.get_children()
    doctor = db.get_primary_doctor() or {}
    return {
        "profile": profile,
        "children": children,
        "doctor": doctor,
    }


@router.post("/profile")
def update_profile(data: ProfileUpdateModel):
    db.save_profile(
        name=data.name,
        monthly_income=data.monthly_income,
        age=data.age,
        city=data.city,
        occupation=data.occupation,
        work_start=data.work_start,
        work_end=data.work_end,
        trusted_contact_name=data.trusted_contact_name,
        trusted_contact_phone=data.trusted_contact_phone,
    )
    return {"status": "success", "message": "Profile saved successfully."}


class PersonaSwitchModel(BaseModel):
    persona: str = "priya"  # 'priya' | 'aarti'


@router.get("/personas")
def get_personas_list():
    """Returns list of available demo personas."""
    return {
        "active_persona": db.get_active_persona(),
        "personas": [
            {
                "id": "priya",
                "name": "Priya (32) & Aarav (4)",
                "occupation": "Office administrator",
                "income": 32000,
                "rent": 9000,
                "school_fees": 4000,
                "story": "Groceries at 80%, overdue MMR vaccine, work-pickup clash.",
            },
            {
                "id": "aarti",
                "name": "Aarti (36) & Veda (12)",
                "occupation": "Govt teacher",
                "income": 65000,
                "rent": 5000,
                "school_fees": 3000,
                "story": "Govt teacher salary Rs 65k, rent Rs 5k, school fees Rs 3k. Board exam evaluation clash with Veda's PTM, Td booster overdue.",
            },
        ],
    }


@router.post("/switch-persona")
def switch_persona(data: PersonaSwitchModel):
    """Switches active demo persona to Priya or Aarti."""
    persona_key = data.persona.lower()
    if persona_key not in ("priya", "aarti"):
        raise HTTPException(status_code=400, detail="Persona must be 'priya' or 'aarti'")
    db.reset_and_seed(persona=persona_key)
    return {
        "status": "success",
        "active_persona": persona_key,
        "message": f"Successfully loaded demo profile for {persona_key.title()}!",
    }


@router.post("/reset-demo")
def reset_demo_data(data: Optional[PersonaSwitchModel] = None):
    """Wipes database and re-seeds active demo family."""
    persona = data.persona if data else db.get_active_persona()
    db.reset_and_seed(persona=persona)
    return {"status": "success", "active_persona": persona, "message": f"Demo data re-seeded for {persona.title()}."}
