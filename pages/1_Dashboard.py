import streamlit as st
import pandas as pd
from utils.supabase_client import fetch_all_expenses, delete_expense_by_id

st.set_page_config(page_title="Dashboard | FinSight AI", page_icon="📊", layout="wide")
st.title("📊 Expense Dashboard")

raw_data = fetch_all_expenses()

if not raw_data:
    st.info("No expense data found in the database. Head over to 'Add Expense' to get started.")
else:
    df = pd.DataFrame(raw_data)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])

    # KPI Metrics Row
    total_spent = df["amount"].sum()
    total_transactions = len(df)
    avg_transaction = df["amount"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Spending", f"₹{total_spent:,.2f}")
    col2.metric("Total Transactions", total_transactions)
    col3.metric("Average Transaction", f"₹{avg_transaction:,.2f}")

    st.divider()
    st.subheader("Recent Transactions")

    display_df = df.sort_values(by="date", ascending=False).copy()
    display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")

    st.dataframe(
        display_df[["id", "date", "category", "amount", "description"]],
        use_container_width=True,
        hide_index=True
    )

    # Delete Action
    st.divider()
    with st.expander("Delete an Entry"):
        record_id = st.number_input("Enter Transaction ID to delete", min_value=1, step=1)
        if st.button("Delete Transaction", type="primary"):
            delete_expense_by_id(record_id)
            st.success(f"Transaction ID {record_id} deleted successfully.")
            st.rerun()