"""
pages/2_Dashboard.py
Today's Card, 30-second Daily Check-in, and Month Overview.
"""

from datetime import date
import streamlit as st
from core import advisor, budget, database as db, health, rules_engine
from utils.helpers import format_currency

st.set_page_config(page_title="Dashboard | SoloMom Advisor", page_icon="🏠", layout="wide")

db.init_db()
if not db.get_profile():
    db.seed_demo_data()

today = db.get_today()
profile = db.get_profile() or {}
name = (profile.get("name") or "Priya").split()[0]

st.title(f"🏠 Welcome back, {name}")
st.caption(f"Today is **{today.strftime('%A, %d %B %Y')}** | SoloMom Advisor Household Memory Active")

# Top Metrics Row
report = budget.build_budget_report()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Monthly Income", format_currency(report["income"]))
m2.metric("Total Planned", format_currency(report["total_planned"]))
m3.metric("Spent So Far", format_currency(report["total_spent"]))
m4.metric("Days Remaining", f"{report['progress']['days_left']} days")

st.divider()

# Section 1: Daily 30-Second Check-in Widget
st.subheader("⚡ 30-Second Daily Check-in")
with st.expander("📝 Quick Daily Log (Sleep, Mood & Expense)", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        sleep_hours = st.number_input("Sleep Last Night (hours)", min_value=0.0, max_value=14.0, value=7.0, step=0.5)
    with c2:
        mood = st.selectbox("Today's Mood", ["good", "okay", "tired", "stressed"], index=1)
    with c3:
        quick_note = st.text_input("Quick Note (optional)", placeholder="Felt busy, good energy...")

    if st.button("Submit Daily Check-in", type="primary"):
        health.log_wellbeing(sleep_hours, mood, quick_note, today)
        st.success("✅ Daily check-in logged!")
        st.rerun()

# Section 2: Proactive Advisor Daily Card
st.subheader("🤖 Today's Advisor Card")

# Generate recommendation card
card = advisor.daily_card(use_llm=True)

st.info(f"**{card['headline']}**\n\n{card['message']}")

if card.get("actions"):
    st.markdown("#### Recommended Actions:")
    cols = st.columns(len(card["actions"]))
    for idx, act in enumerate(card["actions"]):
        with cols[idx]:
            if st.button(f"👉 {act['label']}", key=f"dash_act_{act['id']}"):
                st.session_state["selected_action"] = act['id']
                if act['id'] == "book_vaccine":
                    st.switch_page("pages/6_Advisor.py")
                elif act['id'] == "trim_spending":
                    st.switch_page("pages/3_Money_Plan.py")
                elif act['id'] == "review_schedule":
                    st.switch_page("pages/5_Tasks_Calendar.py")
                else:
                    st.success(f"Action '{act['label']}' marked for attention!")

if card.get("error"):
    st.caption(f"*(Advisor Mode: {card['source']} — {card['error']})*")

st.divider()

# Section 3: Active Flags Overview
st.subheader("🚩 Household Scan Flags")
flags = rules_engine.evaluate_all()
if not flags:
    st.success("✅ Everything looks steady today. No active warnings!")
else:
    for flag in flags:
        severity_color = "🔴" if flag.severity == "high" else "🟡" if flag.severity == "watch" else "🔵"
        st.markdown(f"{severity_color} **[{flag.severity.upper()}] {flag.title}**: {flag.detail}")
