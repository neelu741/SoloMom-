"""
api/routes_doctor.py
FastAPI router for health symptom triage and simulated doctor appointment booking.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from core import database as db, triage

router = APIRouter(prefix="/api/doctor", tags=["doctor"])


class TriageModel(BaseModel):
    symptoms: str
    patient_name: Optional[str] = "child"


class BookingModel(BaseModel):
    slot_time: Optional[str] = "17:30"


@router.post("/triage")
def symptom_triage(item: TriageModel):
    result = triage.triage_symptoms(item.symptoms, patient_name=item.patient_name or "child")
    return result


@router.post("/book")
def book_doctor_appointment(item: BookingModel):
    today = db.get_today()
    booking = triage.execute_doctor_booking(appointment_date=today, slot_time=item.slot_time or "17:30")
    return booking
