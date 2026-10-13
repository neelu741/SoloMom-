"""
pages/4_Health.py
Mother's Wellbeing (sleep/mood logs) & Child's Vaccination Schedule.
"""

import pandas as pd
import streamlit as st
from core import database as db, health
from utils.helpers import status_badge
from utils.safety import MEDICAL_DISCLAIMER

st.set_page_config(page_title="Health & Wellbeing | SoloMom Advisor", page_icon="🩺", layout="wide")

db.init_db()
today = db.get_today()

st.title("🩺 Health & Child Immunization")
st.caption(MEDICAL_DISCLAIMER)

st.divider()

col_wellbeing, col_vaccine = st.columns([5, 5])

# Left Column: Wellbeing & Burnout Monitor
with col_wellbeing:
    st.subheader("🧘 Her Wellbeing & Sleep Log")
    wb_summary = health.get_wellbeing_summary(days=7)
    
    m1, m2 = st.columns(2)
    m1.metric("7-Day Avg Sleep", f"{wb_summary['avg_sleep']} hrs")
    m2.metric("Low Sleep Streak", f"{wb_summary['low_sleep_days']} days", delta="Warning" if wb_summary["sleep_streak_low"] else "OK", delta_color="inverse")

    if wb_summary["sleep_streak_low"]:
        st.warning("⚠️ **Burnout Risk Warning**: Sleep has been under 6 hours for several days in a row. SoloMom Advisor recommends planning a lighter evening!")

    with st.form("log_wellbeing_form"):
        st.write("**Log Today's Wellbeing**")
        sleep_hours = st.slider("Sleep Last Night (hours)", 0.0, 12.0, 6.5, 0.5)
        mood = st.select_slider("Mood", options=["stressed", "tired", "okay", "good"], value="okay")
        note = st.text_input("Notes / Symptoms", placeholder="Headache, felt overworked...")
        
        if st.form_submit_button("Save Wellbeing Log", type="primary"):
            health.log_wellbeing(sleep_hours, mood, note, today)
            st.success("✅ Logged wellbeing entry!")
            st.rerun()

    # Sleep trend chart
    logs = wb_summary["recent_logs"]
    if logs:
        st.write("**Recent Sleep Trend (Last 7 Days)**")
        df_logs = pd.DataFrame(logs)[["log_date", "sleep_hours"]].set_index("log_date")
        st.line_chart(df_logs)

# Right Column: Child Immunization Schedule
with col_vaccine:
    st.subheader("💉 Child Vaccination Tracker")
    children = db.get_children()
    child_name = children[0]["name"] if children else "Child"
    
    st.write(f"Immunization record for **{child_name}**:")
    vaccines = health.get_vaccine_status()
    
    if not vaccines:
        st.info("No vaccination records found.")
    else:
        for v in vaccines:
            given = v["given_date"] is not None
            days_overdue = v["days_overdue"]
            status_str = f"Given on {v['given_date']}" if given else f"{days_overdue} days OVERDUE" if days_overdue > 0 else f"Due on {v['due_date']}"
            
            badge = "🟢 DONE" if given else ("🔴 OVERDUE" if days_overdue > 0 else "🟡 DUE SOON")
            
            with st.container(border=True):
                c1, c2 = st.columns([7, 3])
                with c1:
                    st.markdown(f"**{v['vaccine_name']}** — {badge}")
                    st.caption(f"Due Date: {v['due_date']} | Status: {status_str}")
                with c2:
                    if not given:
                        if st.button("Mark Given", key=f"vac_{v['id']}"):
                            health.mark_vaccine_complete(v["id"])
                            st.success("✅ Marked dose as given!")
                            st.rerun()
                    else:
                        st.write("✅ Completed")
