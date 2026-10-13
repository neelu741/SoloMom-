"""
tests/test_rules_engine.py
Unit test suite for SoloMom Advisor core business logic.
Tests database initialization, rules engine flag evaluation, budget reallocation,
emergency triage detector, and fallback advisor recommendations.
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pytest
except ImportError:
    pytest = None
from core import advisor, budget, database as db, health, planner, replan, rules_engine, triage


def setup_module(module):
    """Setup test environment and seed database."""
    db.reset_and_seed()


def test_database_seeding():
    profile = db.get_profile()
    assert profile is not None
    assert profile["name"] == "Priya"
    assert profile["monthly_income"] == 32000

    children = db.get_children()
    assert len(children) >= 1
    assert children[0]["name"] == "Aarav"


def test_budget_report():
    report = budget.build_budget_report()
    assert report["income"] == 32000
    assert report["total_planned"] == 29500
    assert report["unallocated"] == 2500
    assert len(report["categories"]) > 0


def test_unplanned_expense_reallocation():
    plan = budget.plan_unplanned_expense(500, target_category="Medical Buffer")
    assert plan["amount"] == 500
    assert plan["covered_by_target"] == 0.0 or plan["covered_by_target"] == 500.0
    assert plan["unfunded"] == 0.0


def test_rules_engine_eval():
    flags = rules_engine.evaluate_all()
    assert isinstance(flags, list)
    assert len(flags) > 0

    codes = [f.code for f in flags]
    assert "budget_pace" in codes or "vaccine_overdue" in codes or "low_sleep" in codes


def test_triage_red_flags():
    # Emergency symptom test
    emergency_res = triage.triage_symptoms("Child has high fever with seizure and difficulty breathing")
    assert emergency_res["is_emergency"] is True
    assert emergency_res["doctor_action_offered"] is False

    # Normal symptom test
    normal_res = triage.triage_symptoms("Mild fever and runny nose")
    assert normal_res["is_emergency"] is False
    assert normal_res["doctor_action_offered"] is True


def test_replan_scenario():
    prop = replan.handle_scenario("child_sick")
    assert prop["plan_id"] is not None
    assert prop["status"] == "proposed"
    assert len(prop["summary"]) > 0


def test_advisor_fallback():
    ctx = advisor.build_context()
    rec = advisor.fallback_recommendation(ctx)
    assert "headline" in rec
    assert "message" in rec
    assert "actions" in rec


def test_aarti_persona_seeding():
    db.reset_and_seed(persona="aarti")
    profile = db.get_profile()
    assert profile is not None
    assert profile["name"] == "Aarti"
    assert profile["age"] == 36
    assert profile["occupation"] == "Govt teacher"
    assert profile["monthly_income"] == 65000

    children = db.get_children()
    assert len(children) >= 1
    assert children[0]["name"] == "Veda"
    assert children[0]["age_years"] == 12

    report = budget.build_budget_report()
    assert report["income"] == 65000
    by_cat = {c["category"]: c for c in report["categories"]}
    assert by_cat["Rent"]["planned"] == 5000
    assert by_cat["School & Daycare"]["planned"] == 3000

    flags = rules_engine.evaluate_all()
    assert len(flags) > 0


if __name__ == "__main__":
    setup_module(None)
    test_database_seeding()
    test_budget_report()
    test_unplanned_expense_reallocation()
    test_rules_engine_eval()
    test_triage_red_flags()
    test_replan_scenario()
    test_advisor_fallback()
    test_aarti_persona_seeding()
    print("[SUCCESS] All 8 SoloMom Advisor unit tests passed successfully!")

