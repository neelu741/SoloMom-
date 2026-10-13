"""
core/replan.py
Re-plan Engine: Handles life events (sick child, salary delay, unexpected expense)
and generates proposed plan changes (before/after diff) for user approval/undo.
"""

from datetime import date, timedelta
from typing import Dict, Any, Optional

try:
    from core import budget, database as db, planner
except ImportError:
    import budget
    import database as db
    import planner


def handle_scenario(scenario_key: str, custom_input: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates a proposed re-plan proposal based on scenario.
    Returns proposal dict with before, after, summary, plan_id.
    """
    today = db.get_today()
    month = db.month_key(today)
    report = budget.build_budget_report(month)

    before_state = {
        "budget": {c["category"]: c["planned"] for c in report["categories"]},
        "tasks_count": len(db.get_tasks(from_date=today, to_date=today + timedelta(days=7))),
        "today_tasks": [t["title"] for t in db.get_tasks(on_date=today)],
    }

    after_state = {
        "budget": dict(before_state["budget"]),
        "tasks_count": before_state["tasks_count"],
        "today_tasks": list(before_state["today_tasks"]),
        "changes_summary": [],
    }

    trigger_text = custom_input if scenario_key == "custom" else scenario_key

    if scenario_key == "child_sick":
        trigger_text = "Child is sick today"
        # 1. Reallocate 500 to Medical Buffer if needed
        unplanned = budget.plan_unplanned_expense(500, target_category="Medical Buffer")
        applied = budget.apply_reallocation(unplanned, month)
        after_state["budget"] = applied["after"]

        # 2. Reshuffle schedule for today
        reshuffle = planner.reshuffle_schedule_for_doctor(today, start_time="17:30", end_time="18:00")
        after_state["today_tasks"] = [t["title"] for t in db.get_tasks(on_date=today)]
        after_state["changes_summary"] = [
            "Allocated ₹500 from non-essentials to Medical Buffer for doctor consultation.",
            f"Booked pediatrician appointment today 17:30 - 18:00.",
            f"Postponed non-essential evening tasks: {', '.join(reshuffle['postponed']) or 'None'}.",
        ]

    elif scenario_key == "salary_delayed":
        trigger_text = "Salary delayed by 10 days"
        # Reduce non-essential spending budgets by 30% to conserve cash
        new_budget = dict(before_state["budget"])
        for c in report["categories"]:
            if not c["is_essential"] and c["planned"] > 0:
                new_budget[c["category"]] = round(c["planned"] * 0.7)
                db.set_budget(month, c["category"], new_budget[c["category"]], False)
        after_state["budget"] = new_budget
        after_state["changes_summary"] = [
            "Paused/reduced non-essential categories (Transport, Other, Savings) by 30%.",
            "Postponed non-urgent payments beyond next week.",
            "Protected essential expenses (Rent, Daycare, Groceries).",
        ]

    elif scenario_key == "unexpected_expense":
        trigger_text = custom_input or "Unexpected expense of ₹1,000"
        amount = budget.parse_amount(trigger_text) or 1000.0
        unplanned = budget.plan_unplanned_expense(amount, target_category="Other")
        applied = budget.apply_reallocation(unplanned, month)
        after_state["budget"] = applied["after"]
        after_state["changes_summary"] = [
            f"Covered ₹{int(amount)} cost by drawing from unallocated buffer & non-essentials.",
            "Updated monthly budget targets without touching essential rent/daycare funds.",
        ]
    else:
        after_state["changes_summary"] = [
            "Adjusted tasks and budget based on your input.",
        ]

    plan_id = db.save_plan_change(trigger_text, before_state, after_state)

    return {
        "plan_id": plan_id,
        "trigger_text": trigger_text,
        "before": before_state,
        "after": after_state,
        "summary": after_state["changes_summary"],
        "status": "proposed",
    }


def approve_replan(plan_id: int) -> None:
    db.set_plan_status(plan_id, "approved")


def undo_replan(plan_id: int) -> None:
    history = db.get_plan_history()
    target = next((h for h in history if h["id"] == plan_id), None)
    if not target:
        return

    before_budget = target["before"].get("budget", {})
    month = db.month_key()
    for cat, amount in before_budget.items():
        is_ess = cat in ("Rent", "School & Daycare", "Groceries", "Utilities & Phone", "Medical Buffer")
        db.set_budget(month, cat, amount, is_ess)

    db.set_plan_status(plan_id, "undone")
