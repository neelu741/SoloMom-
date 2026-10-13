"""
pages/3_Money_Plan.py
Monthly money plan: budget allocation, spend tracking, overrun alerts, reallocation.
"""

from datetime import date
import pandas as pd
import streamlit as st
from core import budget, database as db
from utils.helpers import format_currency, status_badge

st.set_page_config(page_title="Money Plan | SoloMom Advisor", page_icon="💰", layout="wide")

db.init_db()
today = db.get_today()
month = db.month_key(today)

st.title("💰 Monthly Money Plan")
st.caption(f"Budget & Expense Tracking for **{today.strftime('%B %Y')}**")

report = budget.build_budget_report(month)

# Financial Summary Cards
c1, c2, c3, c4 = st.columns(4)
c1.metric("Income", format_currency(report["income"]))
c2.metric("Planned Total", format_currency(report["total_planned"]))
c3.metric("Spent Total", format_currency(report["total_spent"]))
c4.metric("Unallocated Buffer", format_currency(report["unallocated"]))

st.divider()

# Left Column: Spend Breakdown & Chart, Right Column: Add Expense & Reallocation
col_left, col_right = st.columns([6, 4])

with col_left:
    st.subheader("📊 Category Budget & Spend Breakdown")
    df = pd.DataFrame(report["categories"])
    if not df.empty:
        # Progress bars table
        for idx, row in df.iterrows():
            status_symbol = status_badge(row["status"])
            st.markdown(f"**{row['category']}** ({'Essential' if row['is_essential'] else 'Non-essential'}) — {status_symbol}")
            pct = min(100.0, float(row['pct_used'])) / 100.0
            st.progress(pct)
            st.caption(f"Spent {format_currency(row['spent'])} of {format_currency(row['planned'])} ({row['pct_used']}%) | Remaining: {format_currency(row['remaining'])} | Daily allowance: {format_currency(row['daily_allowance'])}/day")
            st.write("")

        st.subheader("📈 Budget vs Spent Chart")
        chart_df = df[["category", "planned", "spent"]].set_index("category")
        st.bar_chart(chart_df)

with col_right:
    st.subheader("➕ Log New Expense")
    with st.form("add_expense_form"):
        categories = [c["category"] for c in report["categories"]] or ["Groceries", "Transport", "Other"]
        cat_choice = st.selectbox("Category", categories)
        amount = st.number_input("Amount (₹)", min_value=1.0, value=500.0, step=50.0)
        exp_date = st.date_input("Date Spent", value=today)
        note = st.text_input("Note / Vendor", placeholder="Milk, Vegetables, Cab...")
        is_recurring = st.checkbox("Recurring Monthly Expense")
        
        submitted = st.form_submit_button("Log Expense", type="primary")
        if submitted:
            db.add_expense(cat_choice, amount, exp_date, note, is_recurring)
            st.success(f"✅ Logged {format_currency(amount)} under {cat_choice}")
            st.rerun()

    st.divider()
    st.subheader("🔀 Unexpected Cost Re-allocator")
    st.caption("Life happens. Put in an unexpected cost to see how money can be safely reallocated without touching essential rent or daycare funds.")
    
    unplanned_amt = st.number_input("Unexpected Expense Amount (₹)", min_value=100.0, value=500.0, step=100.0)
    target_cat = st.selectbox("Target Category", ["Medical Buffer", "Other", "Groceries", "Transport"])
    
    plan = budget.plan_unplanned_expense(unplanned_amt, target_category=target_cat)
    st.write(f"**Funding Strategy for {format_currency(unplanned_amt)} ({target_cat}):**")
    st.write(f"- Covered by {target_cat}'s remaining budget: {format_currency(plan['covered_by_target'])}")
    if plan["moves"]:
        st.write("**Proposed Money Reallocations:**")
        for move in plan["moves"]:
            st.markdown(f"  • Take **{format_currency(move['amount'])}** from `{move['from']}` → `{move['to']}`")
    if plan["unfunded"] > 0:
        st.warning(f"⚠️ Unfunded amount: {format_currency(plan['unfunded'])}")

    if st.button("Approve & Apply Reallocation", type="secondary"):
        budget.apply_reallocation(plan)
        st.success("✅ Budget reallocated successfully!")
        st.rerun()
