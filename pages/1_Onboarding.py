"""
pages/1_Onboarding.py
Family profile setup and persistent household memory.
"""

import streamlit as st
from core import database as db

st.set_page_config(page_title="Family Profile | SoloMom Advisor", page_icon="👩‍👧", layout="wide")

st.title("👩‍👧 Family Profile & Memory")
st.markdown("Set up your household memory once. SoloMom Advisor remembers your income, work hours, child details, and doctor's contact.")

# Ensure DB is initialized
db.init_db()
profile = db.get_profile() or {}
children = db.get_children()
doctor = db.get_primary_doctor() or {}

st.subheader("1. Mother's Details")
col1, col2 = st.columns(2)
with col1:
    name = st.text_input("First Name / Full Name", value=profile.get("name", "Priya"))
    age = st.number_input("Age", value=profile.get("age", 32), min_value=18, max_value=100)
    city = st.text_input("City", value=profile.get("city", "Gurgaon"))
    occupation = st.text_input("Occupation", value=profile.get("occupation", "Office administrator"))

with col2:
    monthly_income = st.number_input("Monthly Income (₹)", value=float(profile.get("monthly_income", 32000)), min_value=0.0, step=1000.0)
    work_start = st.text_input("Work Start Time (HH:MM)", value=profile.get("work_start", "09:00"))
    work_end = st.text_input("Work End Time (HH:MM)", value=profile.get("work_end", "18:00"))
    trusted_name = st.text_input("Trusted Emergency Contact Name", value=profile.get("trusted_contact_name", "Sunita (neighbour)"))
    trusted_phone = st.text_input("Trusted Contact Phone", value=profile.get("trusted_contact_phone", "9876543210"))

st.divider()
st.subheader("2. Child Details")
child_name = st.text_input("Child Name", value=children[0]["name"] if children else "Aarav")
child_age = st.number_input("Child Age (Years)", value=children[0]["age_years"] if children else 4, min_value=0, max_value=18)
child_school = st.text_input("School / Daycare Name", value=children[0]["school"] if children else "Little Steps Daycare")

st.divider()
st.subheader("3. Primary Doctor / Clinic")
col3, col4 = st.columns(2)
with col3:
    doc_name = st.text_input("Doctor Name", value=doctor.get("name", "Dr. Sharma"))
    doc_spec = st.text_input("Specialty", value=doctor.get("specialty", "Pediatrician"))
with col4:
    doc_phone = st.text_input("Doctor Phone", value=doctor.get("phone", "9811002233"))
    doc_hours = st.text_input("Clinic Hours", value=doctor.get("clinic_hours", "10:00-13:00, 17:00-20:00"))

if st.button("💾 Save Profile & Household Memory", type="primary"):
    db.save_profile(
        name=name, monthly_income=monthly_income, age=int(age), city=city,
        occupation=occupation, work_start=work_start, work_end=work_end,
        trusted_contact_name=trusted_name, trusted_contact_phone=trusted_phone,
    )
    
    # Save child
    if children:
        # update existing child logic or add
        pass
    else:
        db.add_child(name=child_name, age_years=int(child_age), school=child_school)
        
    # Save doctor
    db.add_doctor(name=doc_name, specialty=doc_spec, phone=doc_phone, clinic_hours=doc_hours, is_primary=True)
    
    st.success("✅ Household profile saved successfully!")

st.info("💡 Demo Tip: Click 'Reset Demo Data' in the left sidebar at any time to reload the pre-seeded demo state (Priya & Aarav).")
