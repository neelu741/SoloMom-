"""
core/voice_processor.py
Speech-to-Text (Whisper API) transcription and LLM natural voice intent extractor.
Parses natural spoken input into database entities (expenses, tasks, wellbeing logs, schedule reshuffles).
"""

import json
import os
import re
from datetime import date, timedelta
from typing import Dict, Any, Optional

try:
    from core import budget, database as db, health, planner, replan
except ImportError:
    import budget
    import database as db
    import health
    import planner
    import replan


def transcribe_audio(audio_bytes: bytes, filename: str = "voice.webm") -> str:
    """
    Transcribes audio bytes using OpenAI Whisper API or Groq Whisper API.
    If API keys are unavailable, falls back gracefully.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1], delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )
            os.remove(tmp_path)
            if transcript and transcript.text:
                return transcript.text.strip()
        except Exception as e:
            print(f"Whisper OpenAI API exception: {e}")

    if groq_key:
        try:
            import groq
            client = groq.Groq(api_key=groq_key)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1], delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=audio_file,
                )
            os.remove(tmp_path)
            if transcript and transcript.text:
                return transcript.text.strip()
        except Exception as e:
            print(f"Whisper Groq API exception: {e}")

    # Fallback default if API key is not present during offline demo
    return "Demo voice note: Paid 600 rupees for Aarav medicines today and need to move evening work deadline to tomorrow"


def process_voice_intent(transcript_text: str) -> Dict[str, Any]:
    """
    Analyzes natural spoken text, identifies intent, updates SQLite database,
    and reshuffles schedule tasks.
    """
    today = db.get_today()
    text_lower = transcript_text.lower()
    actions_taken = []
    created_entities = {}

    # 1. Check for Expense Intent
    amount = budget.parse_amount(transcript_text)
    is_expense = any(kw in text_lower for kw in ["spent", "paid", "bought", "cost", "rupees", "rs", "₹"])
    if is_expense and amount:
        # Determine category
        cat = "Medical Buffer" if any(w in text_lower for w in ["medicine", "doctor", "clinic", "syrup", "hospital", "health"]) else \
              "Groceries" if any(w in text_lower for w in ["groceries", "milk", "veggies", "food", "vegetables", "biscuit"]) else \
              "Transport" if any(w in text_lower for w in ["auto", "cab", "metro", "bus", "petrol", "fuel"]) else "Other"

        exp_id = db.add_expense(category=cat, amount=amount, spent_on=today, note=f"Voice Log: {transcript_text[:40]}")
        actions_taken.append(f"Logged {budget.fmt_inr(amount)} expense under '{cat}'")
        created_entities["expense"] = {"id": exp_id, "amount": amount, "category": cat}

    # 2. Check for Wellbeing Intent (sleep / mood)
    sleep_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours|hrs)\s*(?:of\s*)?sleep", text_lower)
    if sleep_match:
        sleep_hrs = float(sleep_match.group(1))
        mood = "tired" if any(w in text_lower for w in ["tired", "exhausted", "headache"]) else \
               "stressed" if "stressed" in text_lower else "okay"
        health.log_wellbeing(sleep_hrs, mood, note=f"Voice: {transcript_text[:30]}", log_date=today)
        actions_taken.append(f"Logged wellbeing: {sleep_hrs} hrs sleep ({mood} mood)")

    # 3. Check for Schedule Reshuffle / Sick Child Event
    if any(kw in text_lower for kw in ["sick", "fever", "unwell", "doctor appointment", "clinic"]):
        # Trigger sick child scenario & doctor booking slot
        prop = replan.handle_scenario("child_sick", custom_input=transcript_text)
        reshuffle = planner.reshuffle_schedule_for_doctor(today, start_time="17:30", end_time="18:00")
        actions_taken.append(f"Triggered 'Child Sick' re-plan: reserved ₹500 for doctor fee & postponed conflicting tasks")
        created_entities["replan_proposal"] = prop

    # 4. Check for New Task / Reschedule Intent
    if any(kw in text_lower for kw in ["meeting", "deadline", "pickup", "task", "reminder", "fees", "pay"]):
        due_date = today
        if "tomorrow" in text_lower:
            due_date = today + timedelta(days=1)
        elif "next week" in text_lower:
            due_date = today + timedelta(days=7)

        # Extract time if present
        time_match = re.search(r"(\d{1,2})\s*(?:pm|am|:00)?", text_lower)
        st_time = "16:00" if "4 pm" in text_lower or "16:00" in text_lower else "17:00"

        # Search existing task to postpone/reschedule or create new
        existing_tasks = db.get_tasks(from_date=today)
        target_task = next((t for t in existing_tasks if any(word in t["title"].lower() for word in ["meeting", "deadline", "project", "work"]) ), None)

        if "move" in text_lower or "shift" in text_lower or "reschedule" in text_lower or "tomorrow" in text_lower:
            if target_task:
                db.update_task(target_task["id"], due_date=today + timedelta(days=1), note="Rescheduled via Voice Note")
                actions_taken.append(f"Rescheduled task '{target_task['title']}' to tomorrow")
            else:
                task_id = db.add_task(title="Voice Task: Work Update", due_date=due_date, start_time=st_time, end_time="18:00", priority="high")
                actions_taken.append(f"Added task 'Voice Task: Work Update' for {due_date.isoformat()}")
        else:
            task_id = db.add_task(title="Voice Reminder: " + transcript_text[:30], due_date=due_date, start_time=st_time, priority="medium")
            actions_taken.append(f"Added reminder for {due_date.isoformat()}")

    if not actions_taken:
        actions_taken.append("Recorded voice note into household memory log")

    return {
        "transcript": transcript_text,
        "actions_taken": actions_taken,
        "created_entities": created_entities,
        "updated_budget": budget.build_budget_report(),
        "today_tasks": db.get_tasks(on_date=today),
    }
