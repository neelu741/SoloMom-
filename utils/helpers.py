"""
utils/helpers.py
Utility helpers for formatting currency, dates, and status badges.
"""

from datetime import date, datetime
from typing import Optional


def format_currency(amount: float) -> str:
    """Format numbers into Indian Rupee representation (₹)."""
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


def format_date(d: Optional[date] = None, fmt: str = "%d %b %Y") -> str:
    target = d or date.today()
    return target.strftime(fmt)


def status_badge(status: str) -> str:
    status_lower = status.lower()
    if status_lower in ("ok", "good", "done", "approved", "confirmed"):
        return f"🟢 **{status.upper()}**"
    elif status_lower in ("watch", "at_risk", "pending", "proposed", "requested"):
        return f"🟡 **{status.upper()}**"
    elif status_lower in ("high", "over", "overdue", "rejected", "cancelled"):
        return f"🔴 **{status.upper()}**"
    return f"⚪ **{status.upper()}**"
