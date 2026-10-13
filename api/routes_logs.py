"""
api/routes_logs.py
FastAPI router for expenses, wellbeing check-in logs, and vaccine schedule.
"""

from datetime import date
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from core import budget, database as db, health

router = APIRouter(prefix="/api/logs", tags=["logs"])


class ExpenseLogModel(BaseModel):
    category: str
    amount: float
    spent_on: Optional[str] = None  # YYYY-MM-DD
    note: Optional[str] = None
    is_recurring: bool = False


class WellbeingLogModel(BaseModel):
    sleep_hours: float
    mood: str
    note: Optional[str] = None
    log_date: Optional[str] = None


class ReallocateModel(BaseModel):
    amount: float
    target_category: str = "Medical Buffer"


@router.post("/expense")
def add_expense_log(item: ExpenseLogModel):
    spent_date = date.fromisoformat(item.spent_on) if item.spent_on else db.get_today()
    exp_id = db.add_expense(
        category=item.category,
        amount=item.amount,
        spent_on=spent_date,
        note=item.note,
        is_recurring=item.is_recurring,
    )
    return {"status": "success", "expense_id": exp_id}


@router.get("/expenses")
def get_expenses_list(month: Optional[str] = None):
    return db.get_expenses(month)


@router.get("/budget")
def get_budget_report(month: Optional[str] = None):
    return budget.build_budget_report(month)


@router.post("/budget/reallocate")
def reallocate_budget(item: ReallocateModel):
    plan = budget.plan_unplanned_expense(item.amount, target_category=item.target_category)
    result = budget.apply_reallocation(plan)
    return {"status": "success", "plan": plan, "result": result}


@router.post("/wellbeing")
def log_wellbeing_entry(item: WellbeingLogModel):
    log_d = date.fromisoformat(item.log_date) if item.log_date else db.get_today()
    health.log_wellbeing(item.sleep_hours, item.mood, item.note, log_d)
    return {"status": "success", "message": "Wellbeing logged."}


@router.get("/wellbeing")
def get_wellbeing_history(days: int = 7):
    return health.get_wellbeing_summary(days=days)


@router.get("/vaccines")
def get_vaccine_schedule():
    return health.get_vaccine_status()


@router.post("/vaccines/{vaccine_id}/mark-given")
def mark_vaccine_given(vaccine_id: int):
    health.mark_vaccine_complete(vaccine_id)
    return {"status": "success", "vaccine_id": vaccine_id}
