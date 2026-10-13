"""
pages/6_Advisor.py
Interactive AI Advisor Chat, Re-plan Engine (Life scenarios), and Doctor Symptom Triage Flow.
"""

from datetime import date
import streamlit as st
from core import advisor, budget, database as db, replan, triage
from utils.helpers import format_currency
from utils.safety import MEDICAL_DISCLAIMER, render_emergency_alert

st.set_page_config(page_title="AI Advisor & Re-plan | SoloMom Advisor", page_icon="🤖", layout="wide")

db.init_db()
today = db.get_today()
profile = db.get_profile() or {}

st.title("🤖 SoloMom AI Advisor & Re-plan Engine")
st.caption(MEDICAL_DISCLAIMER)

# Tabbed Interface for Advisor Functions
tab_chat, tab_replan, tab_triage = st.tabs(["💬 Advisor Recommendation & Chat", "🔄 Re-plan Engine ('Life Happens')", "🩺 Doctor Symptom Triage"])

# Tab 1: Recommendation & Chat
with tab_chat:
    st.subheader("💡 Today's Advisor Recommendation")
    card = advisor.daily_card(use_llm=True)
    
    st.info(f"### {card['headline']}\n\n{card['message']}")
    
    if card.get("actions"):
        st.markdown("**Quick Actions:**")
        cols = st.columns(len(card["actions"]))
        for idx, act in enumerate(card["actions"]):
            with cols[idx]:
                if st.button(f"👉 {act['label']}", key=f"adv_act_{act['id']}"):
                    st.success(f"Action '{act['label']}' selected!")

    st.divider()
    st.subheader("💬 Ask SoloMom Advisor")
    user_query = st.chat_input("Ask a question about your budget, schedule, or child's care...")
    if user_query:
        st.markdown(f"**You:** {user_query}")
        with st.spinner("Advisor is analyzing your household memory..."):
            ctx = advisor.build_context()
            fallback = advisor.fallback_recommendation(ctx)
            st.markdown(f"**SoloMom Advisor:** {fallback['message']}")

# Tab 2: Re-plan Engine ("Life Happens")
with tab_replan:
    st.subheader("🔄 Re-plan Engine: When Life Changes, Get a Plan to Approve")
    st.write("Single mothers deal with constant unexpected changes. Choose a scenario or describe your situation below to see a proposed **Before vs After** plan.")

    col_scenario, col_diff = st.columns([4, 6])
    
    with col_scenario:
        scenario = st.radio(
            "Select Scenario",
            ["Child is sick today", "Salary delayed by 10 days", "Unexpected expense (e.g. ₹1,000)"],
            index=0
        )
        custom_txt = st.text_input("Or type custom event:", placeholder="Car broke down, working late...")
        
        if st.button("⚡ Generate Proposed Re-plan", type="primary"):
            key = "child_sick" if "sick" in scenario.lower() else "salary_delayed" if "delayed" in scenario.lower() else "unexpected_expense"
            if custom_txt:
                key = "custom"
            
            proposal = replan.handle_scenario(key, custom_input=custom_txt or scenario)
            st.session_state["active_proposal"] = proposal

    with col_diff:
        if "active_proposal" in st.session_state:
            prop = st.session_state["active_proposal"]
            st.markdown(f"### Proposed Plan for: *\"{prop['trigger_text']}\"*")
            st.success("Plan Status: **PROPOSED** (Awaiting Your Approval)")
            
            st.markdown("**Summary of Proposed Changes:**")
            for change in prop["summary"]:
                st.markdown(f"  • {change}")
                
            st.divider()
            c_b, c_a = st.columns(2)
            with c_b:
                st.markdown("**BEFORE (Current Plan)**")
                for cat, amt in prop["before"].get("budget", {}).items():
                    st.caption(f"{cat}: {format_currency(amt)}")
            with c_a:
                st.markdown("**AFTER (Proposed Plan)**")
                for cat, amt in prop["after"].get("budget", {}).items():
                    diff = amt - prop["before"].get("budget", {}).get(cat, amt)
                    diff_str = f" ({'+' if diff>0 else ''}{format_currency(diff)})" if diff != 0 else ""
                    st.caption(f"{cat}: {format_currency(amt)}{diff_str}")

            c_app, c_und = st.columns(2)
            with c_app:
                if st.button("✅ Approve Proposed Plan", type="primary", key="app_plan_btn"):
                    replan.approve_replan(prop["plan_id"])
                    st.success("🎉 Plan approved and applied to your household budget & schedule!")
                    st.rerun()
            with c_und:
                if st.button("❌ Undo / Reject Plan", key="rej_plan_btn"):
                    replan.undo_replan(prop["plan_id"])
                    st.info("Plan rejected and restored to original state.")
                    st.rerun()

# Tab 3: Doctor Symptom Triage Flow (Demo Highlight)
with tab_triage:
    st.subheader("🩺 Family Doctor Action & Symptom Triage (Demo Highlight)")
    st.caption("Quick health triage with safety red-flag checking. Emergency red flags immediately skip booking and urge hospital visit.")

    patient = st.selectbox("Who has symptoms?", ["Child (Aarav)", "Mother (Priya)"])
    symptoms = st.text_area("Describe Symptoms & Duration", placeholder="e.g. Mild fever and cough for 1 day, or high fever with lethargy...")

    if st.button("Run Symptom Triage", type="primary"):
        res = triage.triage_symptoms(symptoms, patient_name=patient)
        st.session_state["triage_result"] = res

    if "triage_result" in st.session_state:
        res = st.session_state["triage_result"]
        if res["is_emergency"]:
            st.error(render_emergency_alert(symptoms))
        else:
            st.warning(f"### {res['headline']}\n\n{res['recommendation']}")
            st.write(f"• **Primary Clinic**: {res['doctor_name']} ({res['clinic_hours']})")
            st.write(f"• **Estimated Fee**: {format_currency(res['estimated_fee'])}")
            
            if res.get("doctor_action_offered"):
                if st.button(f"📅 Book {res['doctor_name']} Today (17:30 - 18:00)", type="primary"):
                    booking = triage.execute_doctor_booking(appointment_date=today, slot_time="17:30")
                    st.success(f"🎉 Appointment requested with {booking['doctor_name']} for today at {booking['time']}!")
                    st.info("• Appointment task created in planner.\n• ₹500 consultation fee reallocated to Medical Buffer.\n• Non-essential conflicting tasks postponed.")
                    st.rerun()
