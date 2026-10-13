"""
utils/safety.py
Safety guidelines, disclaimers, and emergency medical red flag checkers.
"""

MEDICAL_DISCLAIMER = (
    "⚠️ **Medical Safety Disclaimer**: SoloMom Advisor is an AI assistant for organizing family schedules and budget planning. "
    "It is NOT a medical device and DOES NOT provide medical diagnosis or treatment advice. "
    "Always consult a qualified doctor for medical concerns. In an emergency, visit the nearest hospital or call 108."
)

RED_FLAG_KEYWORDS = [
    "chest pain", "difficulty breathing", "breathless", "shortness of breath",
    "seizure", "fits", "unconscious", "fainted", "head injury", "bleeding heavily",
    "stiff neck", "high fever with lethargy", "blue lips", "convulsion"
]


def check_emergency(text: str) -> bool:
    lowered = (text or "").lower()
    return any(k in lowered for k in RED_FLAG_KEYWORDS)


def render_emergency_alert(symptoms: str) -> str:
    return (
        "### 🚨 EMERGENCY MEDICAL ALERT\n\n"
        f"The symptoms described (*\"{symptoms}\"*) match critical medical emergency red flags.\n\n"
        "**IMMEDIATE ACTION REQUIRED:**\n"
        "- **Go to the nearest emergency room or hospital immediately.**\n"
        "- Call Emergency Medical Services (**108** in India).\n"
        "- Call your emergency trusted contact.\n\n"
        "*Regular clinic booking has been bypassed to ensure immediate care.*"
    )
