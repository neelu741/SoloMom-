"""
core/models.py
Data models and schemas for SoloMom Advisor.
"""

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass
class Profile:
    id: int = 1
    name: str = ""
    age: Optional[int] = None
    city: Optional[str] = None
    occupation: Optional[str] = None
    monthly_income: float = 0.0
    work_start: Optional[str] = "09:00"
    work_end: Optional[str] = "18:00"
    trusted_contact_name: Optional[str] = None
    trusted_contact_phone: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Child:
    id: Optional[int] = None
    name: str = ""
    age_years: Optional[int] = None
    school: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Doctor:
    id: Optional[int] = None
    name: str = ""
    specialty: Optional[str] = None
    phone: Optional[str] = None
    clinic_hours: Optional[str] = None
    is_primary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Expense:
    id: Optional[int] = None
    spent_on: str = ""  # YYYY-MM-DD
    category: str = ""
    amount: float = 0.0
    note: Optional[str] = None
    is_recurring: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Task:
    id: Optional[int] = None
    title: str = ""
    kind: str = "task"  # 'task' | 'appointment'
    due_date: str = ""  # YYYY-MM-DD
    start_time: Optional[str] = None  # HH:MM
    end_time: Optional[str] = None    # HH:MM
    priority: str = "medium"  # 'low' | 'medium' | 'high'
    is_essential: bool = False
    status: str = "pending"  # 'pending' | 'done' | 'postponed' | 'requested' | 'confirmed' | 'cancelled'
    assigned_to: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WellbeingLog:
    log_date: str = ""  # YYYY-MM-DD
    sleep_hours: Optional[float] = None
    mood: Optional[str] = None  # 'good' | 'okay' | 'tired' | 'stressed'
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Vaccination:
    id: Optional[int] = None
    child_id: int = 0
    vaccine_name: str = ""
    due_date: str = ""  # YYYY-MM-DD
    given_date: Optional[str] = None  # YYYY-MM-DD
    child_name: Optional[str] = None
    days_overdue: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Flag:
    code: str                 # rule name e.g. schedule_clash, budget_pace
    severity: str             # 'high' | 'watch' | 'info'
    title: str                # short headline
    detail: str               # detailed sentence
    action: str               # UI action key
    impact: float = 0.0       # ordering weight
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplanProposal:
    id: Optional[int] = None
    created_at: str = ""
    trigger_text: str = ""
    before: Dict[str, Any] = field(default_factory=dict)
    after: Dict[str, Any] = field(default_factory=dict)
    status: str = "proposed"  # 'proposed' | 'approved' | 'rejected' | 'undone'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
