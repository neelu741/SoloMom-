"""
SoloMom Advisor — Proactive AI Family Advisor for Single Mothers
Main Streamlit Application Entry Point
"""

import streamlit as st
from core import database as db
from utils.helpers import format_currency

# Page Config
st.set_page_config(
    page_title="SoloMom Advisor",
    page_icon="👩‍👧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database schema & seed demo data if empty
db.init_db()
if not db.get_profile():
    db.seed_demo_data()

profile = db.get_profile() or {}
children = db.get_children()

# Sidebar Setup
with st.sidebar:
    st.image("https://img.icons8.com/illustrations/120/family.png", width=80)
    st.title("SoloMom Advisor")
    st.caption("AI Family Advisor for Single Mothers")
    
    st.divider()
    active_p = db.get_active_persona()
    selected_p = st.selectbox(
        "Choose Demo Family",
        ["Priya (32) & Aarav (4) - Admin", "Aarti (36) & Veda (12) - Govt Teacher"],
        index=0 if active_p == "priya" else 1
    )
    desired_key = "priya" if "Priya" in selected_p else "aarti"
    if desired_key != active_p:
        db.reset_and_seed(persona=desired_key)
        st.success(f"Switched to {desired_key.title()}!")
        st.rerun()

    st.markdown(f"**Persona**: {profile.get('name', 'Priya')} ({profile.get('city', 'Gurgaon')})")
    if children:
        st.markdown(f"**Child**: {children[0]['name']} ({children[0]['age_years']} yrs)")
    st.markdown(f"**Occupation**: {profile.get('occupation', 'Office administrator')}")
    st.markdown(f"**Monthly Income**: {format_currency(profile.get('monthly_income', 32000))}")
    
    st.divider()
    if st.button("🔄 Reset Demo Data", help="Wipe and reload active demo state"):
        db.reset_and_seed(persona=desired_key)
        st.success(f"Demo database re-seeded for {desired_key.title()}!")
        st.rerun()

    st.divider()
    st.caption("Track: AI for Women Empowerment\nSecondary: Financial Independence")

# Home Page Content
st.title("👩‍👧 SoloMom Advisor")
st.subheader("“Every family had an elder who watched over everything. Single mothers don't. We built one.”")

st.markdown("""
Welcome to **SoloMom Advisor**, a proactive AI family advisor that connects money, health, and work-home schedule into one unified, editable plan.

### 🌟 Key MVP Capabilities

- 🏠 **Dashboard**: Today's warm advisor recommendation card & 30-second daily log.
- 💰 **Monthly Money Plan**: Visual budget, spend tracker, overrun alerts & unplanned cost reallocator.
- 🩺 **Health & Vaccines**: Her wellbeing (sleep/mood logs, burnout detector) & child vaccination timeline.
- 📅 **Tasks & Calendar**: Connected work-home weekly schedule & overlap conflict detector.
- 🤖 **AI Advisor & Re-plan**: Proactive chat, scenario re-planning (*"Child is sick"*, *"Salary delayed"*), and symptom triage with doctor booking.
- 📊 **Weekly Review**: Sunday summary of financial adherence, sleep trends, and next week's focus plan.
""")

st.info("👉 Select a page from the sidebar to explore the MVP modules!")
