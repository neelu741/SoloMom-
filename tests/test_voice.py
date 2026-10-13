"""
tests/test_voice.py
Unit test suite for Speech-to-Text Voice Processing and LLM Intent Rescheduler.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import database as db, voice_processor


def test_voice_expense_intent():
    db.reset_and_seed()
    res = voice_processor.process_voice_intent("Paid 600 rupees for Aarav medicines today")
    assert "transcript" in res
    assert len(res["actions_taken"]) > 0
    assert any("600" in a for a in res["actions_taken"])
    assert "expense" in res["created_entities"]


def test_voice_reschedule_intent():
    db.reset_and_seed()
    res = voice_processor.process_voice_intent("Aarav is sick today so move my work project deadline to tomorrow")
    assert "transcript" in res
    assert any("Rescheduled" in a or "re-plan" in a.lower() for a in res["actions_taken"])


def test_voice_wellbeing_intent():
    db.reset_and_seed()
    res = voice_processor.process_voice_intent("Had 5 hours of sleep last night and feeling tired")
    assert any("wellbeing" in a.lower() or "sleep" in a.lower() for a in res["actions_taken"])


if __name__ == "__main__":
    test_voice_expense_intent()
    test_voice_reschedule_intent()
    test_voice_wellbeing_intent()
    print("[SUCCESS] All voice processing & rescheduling unit tests passed successfully!")
