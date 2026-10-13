"""
core/budget.py
Financial math and budget management logic for SoloMom Advisor.
"""

import calendar
import re
from typing import Dict, Any, Optional

try:
    from core import database as db
except ImportError:
    import database as db

FIXED_CATEGORIES = {
    "Rent", "School & Daycare", "Utilities & Phone", "Savings", "Medical Buffer",
}

UNALLOCATED = "Unallocated buffer"
MIN_DAYS_FOR_PACE = 5
PACE_TOLERANCE = 1.10


def fmt_inr(amount: float) -> str:
    """Format float into Indian Rupee string, e.g. 123456 -> '₹1,23,456'."""
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


_AMOUNT_RE = re.compile(r"(?:₹|Rs\.?|INR)?\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE)


def parse_amount(text: str) -> Optional[float]:
    """Extract numeric rupee amount from title/notes."""
    if not text:
        return None
    # Look for currency prefix first
    match = re.search(r"(?:₹|Rs\.?|INR)\s?([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    # Fallback to plain numbers if text contains digits
    match_plain = re.search(r"\b([\d,]{3,})\b", text)
    if match_plain:
        return float(match_plain.group(1).replace(",", ""))
    return None


def month_progress() -> Dict[str, Any]:
    today = db.get_today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return {
        "today": today,
        "days_in_month": days_in_month,
        "days_elapsed": today.day,
        "days_left": days_in_month - today.day,
    }


def build_budget_report(month: Optional[str] = None) -> Dict[str, Any]:
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

        if spent > planned and planned > 0:
            status = "over"
        elif (not fixed and elapsed >= MIN_DAYS_FOR_PACE
              and projected > planned * PACE_TOLERANCE and planned > 0):
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
    """Returns budget summary as Pandas DataFrame."""
    import pandas as pd
    return pd.DataFrame(build_budget_report(month)["categories"])


def plan_unplanned_expense(amount: float, target_category: str = "Medical Buffer",
                           month: Optional[str] = None) -> Dict[str, Any]:
    """Calculate reallocation without modifying DB."""
    report = build_budget_report(month)
    by_name = {c["category"]: c for c in report["categories"]}
    if target_category not in by_name:
        # Create temporary target category if not present
        by_name[target_category] = {"remaining": 0.0, "category": target_category}

    target_remaining = max(0, by_name[target_category].get("remaining", 0))
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


def apply_reallocation(plan: Dict[str, Any], month: Optional[str] = None) -> Dict[str, Any]:
    month = month or db.month_key()
    rows = {r["category"]: dict(r) for r in db.get_budget_summary(month)}
    before = {name: round(r["planned"]) for name, r in rows.items()}
    profile = db.get_profile() or {}
    income = float(profile.get("monthly_income", 0) or 0)

    target_cat = plan.get("target_category", "Medical Buffer")
    if target_cat not in rows:
        db.set_budget(month, target_cat, 0, True)
        rows[target_cat] = {"category": target_cat, "planned": 0.0, "spent": 0.0, "is_essential": 1}

    for move in plan.get("moves", []):
        src, dst, amount = move["from"], move["to"], move["amount"]

        if src == UNALLOCATED:
            free = income - sum(r["planned"] for r in rows.values())
            if free < amount:
                pass # Allow allocation anyway if user explicitly approved
        else:
            if src in rows:
                rows[src]["planned"] = max(rows[src]["spent"], rows[src]["planned"] - amount)
                db.set_budget(month, src, rows[src]["planned"], bool(rows[src]["is_essential"]))

        if dst in rows:
            rows[dst]["planned"] += amount
            db.set_budget(month, dst, rows[dst]["planned"], bool(rows[dst]["is_essential"]))

    after = {name: round(r["planned"]) for name, r in rows.items()}
    return {"before": before, "after": after}
