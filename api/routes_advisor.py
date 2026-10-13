"""
api/routes_advisor.py
FastAPI router for AI Advisor chat, life scenario re-planning, and plan approve/undo.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from core import advisor, replan

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


class ChatMessageModel(BaseModel):
    message: str


class ReplanScenarioModel(BaseModel):
    scenario: str  # 'child_sick' | 'salary_delayed' | 'unexpected_expense' | 'custom'
    custom_input: Optional[str] = None


class PlanActionModel(BaseModel):
    plan_id: int


@router.post("/chat")
def advisor_chat(item: ChatMessageModel):
    ctx = advisor.build_context()
    rec = advisor.fallback_recommendation(ctx)
    return {
        "user_query": item.message,
        "reply": rec["message"],
        "headline": rec["headline"],
        "actions": rec["actions"],
    }


@router.post("/replan")
def generate_replan_proposal(item: ReplanScenarioModel):
    proposal = replan.handle_scenario(item.scenario, custom_input=item.custom_input)
    return proposal


@router.post("/replan/approve")
def approve_replan_proposal(item: PlanActionModel):
    replan.approve_replan(item.plan_id)
    return {"status": "success", "plan_id": item.plan_id, "action": "approved"}


@router.post("/replan/undo")
def undo_replan_proposal(item: PlanActionModel):
    replan.undo_replan(item.plan_id)
    return {"status": "success", "plan_id": item.plan_id, "action": "undone"}
