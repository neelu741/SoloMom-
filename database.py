"""
core/database.py
SQLite layer for SoloMom Advisor (MVP).

Usage
-----
    from core import database as db

    db.init_db()                 # once, at app startup (safe to call repeatedly)
    db.reset_and_seed()          # wipe and load the demo family (Priya + Aarav)

    summary = db.get_budget_summary()
    sleep = db.get_recent_wellbeing(days=7)

Run directly to rebuild the demo database:
    python core/database.py

Design notes
------------
* Standard library only (sqlite3). No ORM, easy to explain in the pitch.
* Dates are ISO strings (YYYY-MM-DD), times are HH:MM, months are YYYY-MM.
* All money math is done here/in Python; the LLM only explains the results.
* Every read helper returns plain dicts, so rules_engine.py and advisor.py
  never touch SQL.
* DEMO DATA IS FICTIONAL. Vaccine names are placeholders: replace them with
  entries from India's official immunization schedule before presenting.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).resolve().parent / "data" / "solomom.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile (
    id                    INTEGER PRIMARY KEY CHECK (id = 1),
    name                  TEXT NOT NULL,
    age                   INTEGER,
    city                  TEXT,
    occupation            TEXT,
    monthly_income        REAL NOT NULL DEFAULT 0,
    work_start            TEXT,
    work_end              TEXT,
    trusted_contact_name  TEXT,
    trusted_contact_phone TEXT
);

CREATE TABLE IF NOT EXISTS children (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    age_years INTEGER,
    school    TEXT
);

CREATE TABLE IF NOT EXISTS doctors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    specialty    TEXT,
    phone        TEXT,
    clinic_hours TEXT,
    is_primary   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS budget_categories (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    month          TEXT NOT NULL,            -- YYYY-MM
    category       TEXT NOT NULL,
    planned_amount REAL NOT NULL CHECK (planned_amount >= 0),
    is_essential   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (month, category)
);

CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    spent_on     TEXT NOT NULL,              -- ISO date
    category     TEXT NOT NULL,
    amount       REAL NOT NULL CHECK (amount >= 0),
    note         TEXT,
    is_recurring INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses (spent_on);

CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'task'
                 CHECK (kind IN ('task', 'appointment')),
    due_date     TEXT NOT NULL,
    start_time   TEXT,
    end_time     TEXT,
    priority     TEXT NOT NULL DEFAULT 'medium'
                 CHECK (priority IN ('low', 'medium', 'high')),
    is_essential INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'done', 'postponed',
                                   'requested', 'confirmed', 'cancelled')),
    assigned_to  TEXT,
    note         TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks (due_date);

CREATE TABLE IF NOT EXISTS wellbeing_logs (
    log_date    TEXT PRIMARY KEY,            -- one entry per day
    sleep_hours REAL CHECK (sleep_hours >= 0 AND sleep_hours <= 24),
    mood        TEXT CHECK (mood IN ('good', 'okay', 'tired', 'stressed')),
    note        TEXT
);

CREATE TABLE IF NOT EXISTS vaccinations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id     INTEGER NOT NULL REFERENCES children (id) ON DELETE CASCADE,
    vaccine_name TEXT NOT NULL,
    due_date     TEXT NOT NULL,
    given_date   TEXT                         -- NULL = not given yet
);

-- Stores every proposed re-plan (before/after) so the user can approve or undo.
CREATE TABLE IF NOT EXISTS plan_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    trigger_text TEXT,
    before_json  TEXT NOT NULL,
    after_json   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'proposed'
                 CHECK (status IN ('proposed', 'approved', 'rejected', 'undone'))
);
"""

_TABLES = [
    "plan_history", "vaccinations", "wellbeing_logs", "tasks", "expenses",
    "budget_categories", "doctors", "children", "profile", "app_state",
]


# --------------------------------------------------------------------------
# Connection helpers
# --------------------------------------------------------------------------
@contextmanager
def db(path: Path = DB_PATH):
    """Open a connection, commit on success, roll back on error, always close."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _fetch(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _fetch_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Optional[dict]:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def init_db() -> None:
    """Create all tables if they do not exist. Safe to call on every start."""
    with db() as conn:
        conn.executescript(SCHEMA)


def reset_db() -> None:
    """Drop every table and recreate the schema (demo reset button)."""
    with db() as conn:
        for table in _TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
    init_db()


# --------------------------------------------------------------------------
# "Today" control (lets the demo run on a fixed day regardless of real date)
# --------------------------------------------------------------------------
def set_today(day: date) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO app_state (key, value) VALUES ('today', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (day.isoformat(),),
        )


def get_today() -> date:
    """Demo date if one was set, otherwise the real date."""
    with db() as conn:
        row = _fetch_one(conn, "SELECT value FROM app_state WHERE key = 'today'")
    return date.fromisoformat(row["value"]) if row else date.today()


def month_key(day: Optional[date] = None) -> str:
    return (day or get_today()).strftime("%Y-%m")


# --------------------------------------------------------------------------
# Profile, child, doctor
# --------------------------------------------------------------------------
def save_profile(name: str, monthly_income: float, age: Optional[int] = None,
                 city: Optional[str] = None, occupation: Optional[str] = None,
                 work_start: Optional[str] = None, work_end: Optional[str] = None,
                 trusted_contact_name: Optional[str] = None,
                 trusted_contact_phone: Optional[str] = None) -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO profile (id, name, age, city, occupation, monthly_income,
                                    work_start, work_end, trusted_contact_name,
                                    trusted_contact_phone)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 name = excluded.name, age = excluded.age, city = excluded.city,
                 occupation = excluded.occupation,
                 monthly_income = excluded.monthly_income,
                 work_start = excluded.work_start, work_end = excluded.work_end,
                 trusted_contact_name = excluded.trusted_contact_name,
                 trusted_contact_phone = excluded.trusted_contact_phone""",
            (name, age, city, occupation, monthly_income, work_start, work_end,
             trusted_contact_name, trusted_contact_phone),
        )


def get_profile() -> Optional[dict]:
    with db() as conn:
        return _fetch_one(conn, "SELECT * FROM profile WHERE id = 1")


def add_child(name: str, age_years: Optional[int] = None,
              school: Optional[str] = None) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO children (name, age_years, school) VALUES (?, ?, ?)",
            (name, age_years, school),
        )
        return cur.lastrowid


def get_children() -> list[dict]:
    with db() as conn:
        return _fetch(conn, "SELECT * FROM children ORDER BY id")


def add_doctor(name: str, specialty: Optional[str] = None,
               phone: Optional[str] = None, clinic_hours: Optional[str] = None,
               is_primary: bool = False) -> int:
    with db() as conn:
        if is_primary:
            conn.execute("UPDATE doctors SET is_primary = 0")
        cur = conn.execute(
            """INSERT INTO doctors (name, specialty, phone, clinic_hours, is_primary)
               VALUES (?, ?, ?, ?, ?)""",
            (name, specialty, phone, clinic_hours, int(is_primary)),
        )
        return cur.lastrowid


def get_primary_doctor() -> Optional[dict]:
    with db() as conn:
        return _fetch_one(
            conn, "SELECT * FROM doctors ORDER BY is_primary DESC, id LIMIT 1")


# --------------------------------------------------------------------------
# Budget and expenses
# --------------------------------------------------------------------------
def set_budget(month: str, category: str, planned_amount: float,
               is_essential: bool = False) -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO budget_categories (month, category, planned_amount, is_essential)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(month, category) DO UPDATE SET
                 planned_amount = excluded.planned_amount,
                 is_essential = excluded.is_essential""",
            (month, category, planned_amount, int(is_essential)),
        )


def add_expense(category: str, amount: float, spent_on: Optional[date] = None,
                note: Optional[str] = None, is_recurring: bool = False) -> int:
    day = (spent_on or get_today()).isoformat()
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO expenses (spent_on, category, amount, note, is_recurring)
               VALUES (?, ?, ?, ?, ?)""",
            (day, category, amount, note, int(is_recurring)),
        )
        return cur.lastrowid


def get_expenses(month: Optional[str] = None) -> list[dict]:
    month = month or month_key()
    with db() as conn:
        return _fetch(
            conn,
            "SELECT * FROM expenses WHERE substr(spent_on, 1, 7) = ? "
            "ORDER BY spent_on, id",
            (month,),
        )


def get_budget_summary(month: Optional[str] = None) -> list[dict]:
    """
    One row per category: planned, spent, remaining, pct_used, is_essential.
    This is the single source of truth for budget numbers.
    """
    month = month or month_key()
    with db() as conn:
        rows = _fetch(
            conn,
            """SELECT b.category, b.planned_amount AS planned, b.is_essential,
                      COALESCE(SUM(e.amount), 0) AS spent
               FROM budget_categories b
               LEFT JOIN expenses e
                 ON e.category = b.category AND substr(e.spent_on, 1, 7) = b.month
               WHERE b.month = ?
               GROUP BY b.id
               ORDER BY b.id""",
            (month,),
        )
    for r in rows:
        r["remaining"] = r["planned"] - r["spent"]
        r["pct_used"] = round(100 * r["spent"] / r["planned"], 1) if r["planned"] else 0.0
    return rows


# --------------------------------------------------------------------------
# Tasks and appointments
# --------------------------------------------------------------------------
_TASK_FIELDS = {"title", "kind", "due_date", "start_time", "end_time", "priority",
                "is_essential", "status", "assigned_to", "note"}


def add_task(title: str, due_date: date, kind: str = "task",
             start_time: Optional[str] = None, end_time: Optional[str] = None,
             priority: str = "medium", is_essential: bool = False,
             status: str = "pending", assigned_to: Optional[str] = None,
             note: Optional[str] = None) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO tasks (title, kind, due_date, start_time, end_time,
                                  priority, is_essential, status, assigned_to, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, kind, due_date.isoformat(), start_time, end_time, priority,
             int(is_essential), status, assigned_to, note),
        )
        return cur.lastrowid


def get_tasks(status: Optional[str] = None, on_date: Optional[date] = None,
              from_date: Optional[date] = None,
              to_date: Optional[date] = None) -> list[dict]:
    sql, params = "SELECT * FROM tasks WHERE 1=1", []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if on_date:
        sql += " AND due_date = ?"
        params.append(on_date.isoformat())
    if from_date:
        sql += " AND due_date >= ?"
        params.append(from_date.isoformat())
    if to_date:
        sql += " AND due_date <= ?"
        params.append(to_date.isoformat())
    sql += " ORDER BY due_date, COALESCE(start_time, '99:99'), id"
    with db() as conn:
        return _fetch(conn, sql, tuple(params))


def update_task(task_id: int, **fields: Any) -> None:
    """Update allowed fields only, e.g. update_task(3, status='postponed')."""
    clean = {k: v for k, v in fields.items() if k in _TASK_FIELDS}
    if not clean:
        raise ValueError("No valid task fields to update.")
    for key, value in list(clean.items()):
        if isinstance(value, date):
            clean[key] = value.isoformat()
        elif isinstance(value, bool):
            clean[key] = int(value)
    assignments = ", ".join(f"{k} = ?" for k in clean)
    with db() as conn:
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id = ?",
                     (*clean.values(), task_id))


# --------------------------------------------------------------------------
# Wellbeing (sleep and mood, self-reported)
# --------------------------------------------------------------------------
def upsert_wellbeing(log_date: date, sleep_hours: Optional[float] = None,
                     mood: Optional[str] = None, note: Optional[str] = None) -> None:
    """One entry per day; logging again the same day overwrites it."""
    with db() as conn:
        conn.execute(
            """INSERT INTO wellbeing_logs (log_date, sleep_hours, mood, note)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(log_date) DO UPDATE SET
                 sleep_hours = excluded.sleep_hours,
                 mood = excluded.mood, note = excluded.note""",
            (log_date.isoformat(), sleep_hours, mood, note),
        )


def get_recent_wellbeing(days: int = 7) -> list[dict]:
    """Logs from the last `days` days up to today, newest first."""
    today = get_today()
    start = today - timedelta(days=days - 1)
    with db() as conn:
        return _fetch(
            conn,
            "SELECT * FROM wellbeing_logs WHERE log_date BETWEEN ? AND ? "
            "ORDER BY log_date DESC",
            (start.isoformat(), today.isoformat()),
        )


# --------------------------------------------------------------------------
# Vaccinations
# --------------------------------------------------------------------------
def add_vaccination(child_id: int, vaccine_name: str, due_date: date,
                    given_date: Optional[date] = None) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO vaccinations (child_id, vaccine_name, due_date, given_date)
               VALUES (?, ?, ?, ?)""",
            (child_id, vaccine_name, due_date.isoformat(),
             given_date.isoformat() if given_date else None),
        )
        return cur.lastrowid


def mark_vaccination_given(vaccination_id: int, given_date: Optional[date] = None) -> None:
    with db() as conn:
        conn.execute("UPDATE vaccinations SET given_date = ? WHERE id = ?",
                     ((given_date or get_today()).isoformat(), vaccination_id))


def get_vaccinations(child_id: Optional[int] = None) -> list[dict]:
    """Each row includes days_overdue (0 if not overdue or already given)."""
    sql = ("SELECT v.*, c.name AS child_name FROM vaccinations v "
           "JOIN children c ON c.id = v.child_id")
    params: tuple = ()
    if child_id is not None:
        sql += " WHERE v.child_id = ?"
        params = (child_id,)
    sql += " ORDER BY v.due_date"
    with db() as conn:
        rows = _fetch(conn, sql, params)
    today = get_today()
    for r in rows:
        overdue = 0
        if r["given_date"] is None:
            overdue = max(0, (today - date.fromisoformat(r["due_date"])).days)
        r["days_overdue"] = overdue
    return rows


# --------------------------------------------------------------------------
# Plan history (re-plan proposals, approval and undo)
# --------------------------------------------------------------------------
def save_plan_change(trigger_text: str, before: dict, after: dict) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO plan_history (created_at, trigger_text, before_json, after_json)
               VALUES (?, ?, ?, ?)""",
            (datetime.now().isoformat(timespec="seconds"), trigger_text,
             json.dumps(before), json.dumps(after)),
        )
        return cur.lastrowid


def set_plan_status(plan_id: int, status: str) -> None:
    with db() as conn:
        conn.execute("UPDATE plan_history SET status = ? WHERE id = ?",
                     (status, plan_id))


def get_plan_history(limit: int = 20) -> list[dict]:
    with db() as conn:
        rows = _fetch(conn, "SELECT * FROM plan_history ORDER BY id DESC LIMIT ?",
                      (limit,))
    for r in rows:
        r["before"] = json.loads(r.pop("before_json"))
        r["after"] = json.loads(r.pop("after_json"))
    return rows


# --------------------------------------------------------------------------
# Demo data (fictional family: Priya + Aarav)
# --------------------------------------------------------------------------
def seed_demo_data() -> None:
    """
    Story: day 18 of the month. Groceries are at 80% with 12 days left, school
    fees are due tomorrow, Aarav's vaccine dose is 12 days overdue, Priya's
    sleep has dropped for several days, and there is a work-pickup clash today.
    """
    month_start = date.today().replace(day=1)
    today = month_start + timedelta(days=17)  # "day 18"
    set_today(today)
    month = month_key(today)

    save_profile(
        name="Priya", age=32, city="Gurgaon", occupation="Office administrator",
        monthly_income=32000, work_start="09:00", work_end="18:00",
        trusted_contact_name="Sunita (neighbour)", trusted_contact_phone="9000000001",
    )
    child_id = add_child("Aarav", age_years=4, school="Little Steps Daycare")
    add_doctor("Dr. Sharma", specialty="Pediatrician", phone="9000000002",
               clinic_hours="10:00-13:00, 17:00-20:00", is_primary=True)

    # Budget plan: totals 29,500 of 32,000 income, ~2,500 unallocated buffer.
    for category, amount, essential in [
        ("Rent", 9000, True), ("School & Daycare", 4000, True),
        ("Groceries", 6000, True), ("Transport", 2000, False),
        ("Utilities & Phone", 2000, True), ("Medical Buffer", 1500, True),
        ("Savings", 3000, False), ("Other", 2000, False),
    ]:
        set_budget(month, category, amount, essential)

    # (day offset from month start, category, amount, note, recurring)
    expenses = [
        (0, "Rent", 9000, "Monthly rent", True),
        (4, "Utilities & Phone", 1800, "Electricity + phone recharge", False),
        (1, "Groceries", 900, "Weekly groceries", False),
        (4, "Groceries", 750, "Vegetables and milk", False),
        (8, "Groceries", 1200, "Monthly staples", False),
        (11, "Groceries", 650, "Weekly groceries", False),
        (14, "Groceries", 800, "Fruits and snacks", False),
        (16, "Groceries", 500, "Top-up", False),
        (2, "Transport", 400, "Auto/metro", False),
        (6, "Transport", 350, "Auto/metro", False),
        (10, "Transport", 500, "Cab", False),
        (15, "Transport", 300, "Auto/metro", False),
        (3, "Other", 600, "Outing", False),
        (9, "Other", 450, "Toy for Aarav", False),
        (13, "Other", 700, "Household items", False),
    ]
    for offset, category, amount, note, recurring in expenses:
        add_expense(category, amount, month_start + timedelta(days=offset), note, recurring)

    # Tasks and appointments around "today"
    add_task("Pay school fees (Rs 4,000)", today + timedelta(days=1),
             priority="high", is_essential=True)
    add_task("Project deadline (work)", today, start_time="15:00", end_time="19:00",
             priority="high", is_essential=True)
    add_task("Team meeting", today, kind="appointment", start_time="17:00",
             end_time="18:00", priority="medium")
    add_task("Aarav school pickup", today, start_time="17:30", end_time="18:00",
             priority="high", is_essential=True, assigned_to="Priya")
    add_task("Grocery top-up", today + timedelta(days=2), priority="low")

    # Wellbeing: last 10 days, sleep trending down
    sleep = [7, 7, 6.5, 6.5, 6.5, 6, 5.5, 5.5, 5, 5.5]
    moods = ["okay", "okay", "okay", "okay", "tired", "tired", "tired",
             "stressed", "tired", "tired"]
    for i, (hours, mood) in enumerate(zip(sleep, moods)):
        upsert_wellbeing(today - timedelta(days=9 - i), hours, mood)

    # Vaccines. NAMES ARE PLACEHOLDERS: replace with official schedule entries.
    add_vaccination(child_id, "Routine dose (placeholder, see official schedule)",
                    today - timedelta(days=120), today - timedelta(days=118))
    add_vaccination(child_id, "Due dose (placeholder, see official schedule)",
                    today - timedelta(days=12), None)


def reset_and_seed() -> None:
    reset_db()
    seed_demo_data()


if __name__ == "__main__":
    reset_and_seed()
    print(f"Demo database created at {DB_PATH}")
    print("Today (demo):", get_today())
    for row in get_budget_summary():
        print(f"  {row['category']:<18} spent {row['spent']:>7.0f} / {row['planned']:>6.0f}"
              f"  ({row['pct_used']}%)")
    print("Overdue vaccines:",
          [v["vaccine_name"] for v in get_vaccinations() if v["days_overdue"] > 0])
    print("Sleep (last 7 days):", [w["sleep_hours"] for w in get_recent_wellbeing(7)])