"""
core/budget.py
All money math for SoloMom Advisor. Pure Python on top of core/database.py.

Principle: every rupee figure the advisor ever mentions is calculated HERE.
The LLM only explains these numbers; it never computes them.

Main entry points
-----------------
    build_budget_report()          -> per-category status, projections, totals
    plan_unplanned_expense(amount) -> where the money could come from (not applied)
    apply_reallocation(plan)       -> applies an approved plan, returns before/after
    fmt_inr(amount)                -> "Rs 1,23,456" style text for the UI
"""

import calendar
import re
from typing import Optional

import database as db

# Categories that are paid in lumps or on due dates, so "pace" is meaningless.
# They are only flagged if spending exceeds the plan.
FIXED_CATEGORIES = {
    "Rent", "School & Daycare", "Utilities & Phone", "Savings", "Medical Buffer",
}

UNALLOCATED = "Unallocated buffer"
MIN_DAYS_FOR_PACE = 5      # don't judge pace in the first days of a month
PACE_TOLERANCE = 1.10      # projected spend may exceed plan by 10% before flagging


# --------------------------------------------------------------------------
# Formatting and parsing helpers
# --------------------------------------------------------------------------
def fmt_inr(amount: float) -> str:
    """Format with Indian digit grouping, e.g. 123456 -> '₹1,23,456'."""
    n = int(round(amount))
    sign = "-" if n < 0 else ""
    digits = str(abs(n))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    return f"{sign}₹{digits}"


_AMOUNT_RE = re.compile(r"(?:₹|Rs\.?|INR)\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE)


def parse_amount(text: str) -> Optional[float]:
    """Pull a rupee amount out of text like 'Pay school fees (Rs 4,000)'."""
    match = _AMOUNT_RE.search(text or "")
    return float(match.group(1).replace(",", "")) if match else None


# --------------------------------------------------------------------------
# Month progress and the main report
# --------------------------------------------------------------------------
def month_progress() -> dict:
    today = db.get_today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return {
        "today": today,
        "days_in_month": days_in_month,
        "days_elapsed": today.day,
        "days_left": days_in_month - today.day,
    }


def build_budget_report(month: Optional[str] = None) -> dict:
    """
    Per-category status plus totals.

    status:
      'over'     spent more than planned
      'at_risk'  variable category whose current pace would exceed the plan
      'ok'       everything else
    """
    month = month or db.month_key()
    progress = month_progress()
    elapsed, days_in_month, days_left = (
        progress["days_elapsed"], progress["days_in_month"], progress["days_left"])
    profile = db.get_profile() or {}
    income = float(profile.get("monthly_income", 0) or 0)

    categories = []
    for row in db.get_budget_summary(month):
        planned, spent = row["planned"], row["spent"]
        fixed = row["category"] in FIXED_CATEGORIES
        projected = spent if fixed else (spent / max(elapsed, 1)) * days_in_month

        if spent > planned:
            status = "over"
        elif (not fixed and elapsed >= MIN_DAYS_FOR_PACE
              and projected > planned * PACE_TOLERANCE):
            status = "at_risk"
        else:
            status = "ok"

        remaining = planned - spent
        categories.append({
            "category": row["category"],
            "planned": round(planned),
            "spent": round(spent),
            "remaining": round(remaining),
            "pct_used": row["pct_used"],
            "is_essential": bool(row["is_essential"]),
            "is_fixed": fixed,
            "projected_total": round(projected),
            "projected_overrun": round(max(0.0, projected - planned)),
            "daily_allowance": round(remaining / days_left) if days_left > 0 and remaining > 0 else 0,
            "status": status,
        })

    total_planned = sum(c["planned"] for c in categories)
    total_spent = sum(c["spent"] for c in categories)
    return {
        "month": month,
        "progress": progress,
        "income": round(income),
        "total_planned": total_planned,
        "total_spent": total_spent,
        "unallocated": round(income - total_planned),
        "categories": categories,
        "flagged": sorted(
            (c for c in categories if c["status"] in ("over", "at_risk")),
            key=lambda c: c["projected_overrun"], reverse=True),
    }


def budget_dataframe(month: Optional[str] = None):
    """Report as a pandas DataFrame for Streamlit charts (pandas imported lazily)."""
    import pandas as pd
    return pd.DataFrame(build_budget_report(month)["categories"])


# --------------------------------------------------------------------------
# Unplanned expenses (e.g. a doctor visit) and re-allocation
# --------------------------------------------------------------------------
def plan_unplanned_expense(amount: float, target_category: str = "Medical Buffer",
                           month: Optional[str] = None) -> dict:
    """
    Work out how to fund an unexpected cost. Nothing is changed here.

    Order of funding:
      1. the target category's own remaining budget
      2. the unallocated buffer (income not yet planned)
      3. non-essential categories with money left (largest remaining first)
    Essential categories are never touched.
    """
    report = build_budget_report(month)
    by_name = {c["category"]: c for c in report["categories"]}
    if target_category not in by_name:
        raise ValueError(f"Unknown budget category: {target_category}")

    target_remaining = max(0, by_name[target_category]["remaining"])
    covered_by_target = min(amount, target_remaining)
    shortfall = amount - covered_by_target
    moves = []

    take = min(max(0, report["unallocated"]), shortfall)
    if take > 0:
        moves.append({"from": UNALLOCATED, "to": target_category, "amount": round(take)})
        shortfall -= take

    donors = sorted(
        (c for c in report["categories"]
         if not c["is_essential"] and c["category"] != target_category and c["remaining"] > 0),
        key=lambda c: c["remaining"], reverse=True)
    for donor in donors:
        if shortfall <= 0:
            break
        take = min(donor["remaining"], shortfall)
        moves.append({"from": donor["category"], "to": target_category, "amount": round(take)})
        shortfall -= take

    return {
        "amount": round(amount),
        "target_category": target_category,
        "covered_by_target": round(covered_by_target),
        "moves": moves,
        "unfunded": round(max(0, shortfall)),
    }


def apply_reallocation(plan: dict, month: Optional[str] = None) -> dict:
    """
    Apply an approved plan from plan_unplanned_expense().
    Returns {'before': {...}, 'after': {...}} of planned amounts, ready for
    database.save_plan_change(). Raises ValueError rather than breaking a rule.
    """
    month = month or db.month_key()
    rows = {r["category"]: dict(r) for r in db.get_budget_summary(month)}
    before = {name: round(r["planned"]) for name, r in rows.items()}
    profile = db.get_profile() or {}
    income = float(profile.get("monthly_income", 0) or 0)

    for move in plan["moves"]:
        src, dst, amount = move["from"], move["to"], move["amount"]
        if dst not in rows:
            raise ValueError(f"Unknown budget category: {dst}")

        if src == UNALLOCATED:
            free = income - sum(r["planned"] for r in rows.values())
            if free < amount:
                raise ValueError("Not enough unallocated buffer.")
        else:
            if src not in rows:
                raise ValueError(f"Unknown budget category: {src}")
            if rows[src]["is_essential"]:
                raise ValueError(f"'{src}' is essential and protected.")
            if rows[src]["planned"] - amount < rows[src]["spent"]:
                raise ValueError(f"'{src}' cannot go below what is already spent.")
            rows[src]["planned"] -= amount
            db.set_budget(month, src, rows[src]["planned"], bool(rows[src]["is_essential"]))

        rows[dst]["planned"] += amount
        db.set_budget(month, dst, rows[dst]["planned"], bool(rows[dst]["is_essential"]))

    after = {name: round(r["planned"]) for name, r in rows.items()}
    return {"before": before, "after": after}


if __name__ == "__main__":
    db.init_db()
    if not db.get_profile() and not db.get_budget_summary():
        db.seed_demo_data()

    report = build_budget_report()
    print(f"Day {report['progress']['days_elapsed']} of {report['progress']['days_in_month']}"
          f" | planned {fmt_inr(report['total_planned'])} of income {fmt_inr(report['income'])}"
          f" | unallocated {fmt_inr(report['unallocated'])}")
    for c in report["categories"]:
        print(f"  {c['category']:<18} {fmt_inr(c['spent']):>8} / {fmt_inr(c['planned']):>8}"
              f"  {c['status']:<8} projected {fmt_inr(c['projected_total'])}")
    print("Doctor visit plan:", plan_unplanned_expense(500))