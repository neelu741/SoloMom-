"""
pages/5_Tasks_Calendar.py
Work-Home Weekly Planner, Schedule Conflict Detector, and Task Reshuffling.
"""

from datetime import date, timedelta
import streamlit as st
from core import database as db, planner
from utils.helpers import status_badge

st.set_page_config(page_title="Tasks & Calendar | SoloMom Advisor", page_icon="📅", layout="wide")

db.init_db()
today = db.get_today()

st.title("📅 Work-Home Weekly Planner")
st.caption(f"Connected schedule for work commitments, child daycare/school pickups, and household tasks.")

# Section 1: Schedule Conflict Alerts
conflicts = planner.check_schedule_conflicts(lookahead_days=2)
if conflicts:
    for c in conflicts:
        st.warning(f"⚠️ **Schedule Conflict Detected on {c['date']}**:")
        for t in c["tasks"]:
            st.markdown(f"  • **{t['title']}** ({t.get('start_time','--')}-{t.get('end_time','--')}) — Priority: `{t['priority']}` | Essential: `{t['is_essential']}`")

st.divider()

col_schedule, col_add = st.columns([7, 3])

with col_schedule:
    st.subheader("🗓️ Next 7 Days Tasks & Appointments")
    tasks = db.get_tasks(from_date=today, to_date=today + timedelta(days=7))
    
    if not tasks:
        st.info("No tasks scheduled for the upcoming week.")
    else:
        # Group tasks by due date
        by_date = {}
        for t in tasks:
            by_date.setdefault(t["due_date"], []).append(t)
            
        for day_str in sorted(by_date.keys()):
            d_obj = date.fromisoformat(day_str)
            is_today = d_obj == today
            st.markdown(f"#### {'⭐ TODAY - ' if is_today else ''}{d_obj.strftime('%A, %d %b %Y')}")
            
            for t in by_date[day_str]:
                time_slot = f"{t['start_time']} - {t['end_time']}" if t.get("start_time") else "All day"
                badge = status_badge(t["status"])
                kind_icon = "🩺" if t["kind"] == "appointment" else "📌"
                essential_tag = " [ESSENTIAL]" if t["is_essential"] else ""
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([5, 3, 2])
                    with c1:
                        st.markdown(f"{kind_icon} **{t['title']}**{essential_tag}")
                        st.caption(f"Time: {time_slot} | Assigned: {t.get('assigned_to') or 'Unassigned'}")
                    with c2:
                        st.markdown(f"Status: {badge}")
                    with c3:
                        new_status = st.selectbox("Update", ["pending", "done", "postponed", "cancelled"], index=["pending", "done", "postponed", "cancelled"].index(t["status"]) if t["status"] in ["pending", "done", "postponed", "cancelled"] else 0, key=f"t_sel_{t['id']}")
                        if new_status != t["status"]:
                            db.update_task(t["id"], status=new_status)
                            st.rerun()

with col_add:
    st.subheader("➕ Add Task / Appointment")
    with st.form("new_task_form"):
        title = st.text_input("Title", placeholder="Pay electricity bill, Team Sync...")
        kind = st.selectbox("Kind", ["task", "appointment"])
        due_d = st.date_input("Due Date", value=today)
        st_time = st.text_input("Start Time (HH:MM optional)", value="17:00")
        end_time = st.text_input("End Time (HH:MM optional)", value="18:00")
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=1)
        is_essential = st.checkbox("Essential Task (Protected)")
        assigned_to = st.text_input("Assigned To", value="Priya")
        note = st.text_input("Notes", placeholder="Bring receipt...")

        if st.form_submit_button("Add to Planner", type="primary"):
            if not title:
                st.error("Please enter a title.")
            else:
                db.add_task(
                    title=title, due_date=due_d, kind=kind,
                    start_time=st_time if st_time else None,
                    end_time=end_time if end_time else None,
                    priority=priority, is_essential=is_essential,
                    assigned_to=assigned_to, note=note
                )
                st.success(f"✅ Added '{title}' to schedule!")
                st.rerun()
