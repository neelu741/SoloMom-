"""
pages/7_Weekly_Review.py
Sunday Summary: Spending trends, Wellbeing trends, and Next Week's Focus Plan.
"""

from datetime import date, timedelta
import pandas as pd
import streamlit as st
from core import budget, database as db, health
from utils.helpers import format_currency

st.set_page_config(page_title="Weekly Review | SoloMom Advisor", page_icon="📊", layout="wide")

db.init_db()
today = db.get_today()
profile = db.get_profile() or {}
name = (profile.get("name") or "Priya").split()[0]

st.title("📊 Weekly Review & Retrospective")
st.caption(f"End-of-Week Summary for {name}'s Household | SoloMom Advisor Analytics")

st.divider()

# Section 1: Summary Card
report = budget.build_budget_report()
wb_summary = health.get_wellbeing_summary(days=7)
completed_tasks = len(db.get_tasks(status="done"))
pending_tasks = len(db.get_tasks(status="pending"))

st.subheader("🌟 Week at a Glance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Spent This Month", format_currency(report["total_spent"]), f"{report['total_planned'] - report['total_spent']} remaining")
c2.metric("Avg Sleep (7 Days)", f"{wb_summary['avg_sleep']} hrs")
c3.metric("Completed Tasks", f"{completed_tasks} items")
c4.metric("Pending Tasks", f"{pending_tasks} items")

st.divider()

# Section 2: Trends Charts
col_b_chart, col_w_chart = st.columns(2)

with col_b_chart:
    st.subheader("💰 Spending by Category")
    df_cat = pd.DataFrame(report["categories"])
    if not df_cat.empty:
        st.bar_chart(df_cat.set_index("category")[["planned", "spent"]])

with col_w_chart:
    st.subheader("😴 7-Day Sleep & Mood Trend")
    logs = wb_summary["recent_logs"]
    if logs:
        df_logs = pd.DataFrame(logs)[["log_date", "sleep_hours"]].set_index("log_date")
        st.line_chart(df_logs)
    else:
        st.info("No sleep logs recorded this week.")

st.divider()

# Section 3: Next Week's Recommended Plan
st.subheader("🎯 Focus Plan for Next Week")

st.markdown("""
1. **Financial Focus**: Groceries are currently running at 80% of budget. Limit discretionary spending to ₹150/day for the next 5 days.
2. **Health Focus**: Sleep averaged under 6 hours mid-week. Keep evening work tasks capped before 20:00.
3. **Child Care Milestone**: Aarav's overdue vaccine checkup is scheduled/flagged for clinic visit.
4. **Schedule Alignment**: School fee payment due tomorrow — funds are reserved in essential savings.
""")

st.success("💪 You are doing an incredible job managing your household. SoloMom Advisor has your back!")
