# SoloMom Advisor

> *"Every family had an elder who watched over everything. Single mothers don't. We built one."*

**Track**: AI for Women Empowerment (Secondary Fit: Financial Independence)

---

## 📌 Problem & Solution

### Problem
A single mother handles income, child care, health, doctor appointments, and household chores entirely alone. Fragmented apps handle budget, health, or to-do lists independently without connecting them. She has no unified advisor that sees the complete picture and intervenes proactively before burnout or financial overruns occur.

### Solution
**SoloMom Advisor** is a proactive AI family advisor that:
- Retains household memory (income, fixed costs, child details, primary doctor, work hours).
- Cross-connects money, health, and schedule.
- Scans data with deterministic rules and generates one warm, grounded recommendation.
- Acts on recommendations with explicit mother approval (editable plans, before/after diffs, and undo controls).

---

## 🛠️ Tech Stack & MVP Architecture

- **UI**: Streamlit Multi-Page Framework
- **Backend & Memory**: Python 3.12, SQLite (`data/solomom.db`)
- **Data Logic**: Pandas, NumPy
- **Advisor Engine**: Rule Evaluation Engine + Grounded Hosted LLM API (Gemini / OpenAI API) with deterministic fallback
- **Safety**: Red-flag medical emergency triage detector

---

## 🚀 Quick Start Guide

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys (Optional)
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_api_key_here
```
*(If no API key is provided, SoloMom Advisor operates seamlessly using its deterministic rule-based advice fallback engine!)*

### 3. Run Application
```bash
streamlit run app.py
```

---

## 📁 Directory Layout

```
solomom-advisor/
├── app.py                    # Streamlit entry point, page navigation
├── requirements.txt
├── README.md
│
├── pages/                    # Multi-page views
│   ├── 1_Onboarding.py       # Family profile setup
│   ├── 2_Dashboard.py        # Today's card + month view
│   ├── 3_Money_Plan.py       # Budget, manual expense entry
│   ├── 4_Health.py           # Her wellbeing + child vaccines
│   ├── 5_Tasks_Calendar.py   # Appointments and tasks
│   ├── 6_Advisor.py          # Chat, re-plan, doctor flow
│   └── 7_Weekly_Review.py    # Sunday summary
│
├── core/                     # Business logic
│   ├── database.py           # SQLite setup and queries
│   ├── models.py             # Data schemas
│   ├── budget.py             # Budget split, overrun checks
│   ├── health.py             # Vaccine schedule, wellbeing trends
│   ├── planner.py            # Weekly schedule logic
│   ├── rules_engine.py       # Flags: overspend, missed checkup, overload
│   ├── advisor.py            # Turns flags into recommendations
│   ├── replan.py             # Situation → JSON changes → diff
│   ├── triage.py             # Red-flag check & doctor booking
│   └── llm_client.py         # LLM API wrapper
│
├── prompts/                  # Prompt templates
│   ├── advisor_prompt.txt
│   ├── replan_prompt.txt
│   ├── triage_prompt.txt
│   └── weekly_summary_prompt.txt
│
├── data/
│   ├── solomom.db            # SQLite database
│   ├── sample_profile.json   # Demo data
│   └── vaccine_schedule.json # Child immunization schedule
│
└── utils/
    ├── helpers.py            # Currency (₹), date formatting
    └── safety.py             # Medical disclaimer & red flags
```
