import streamlit as st
import pandas as pd
from datetime import date
import plotly.express as px
from supabase import create_client

st.set_page_config(page_title="Expense Tracker", layout="wide")

# -------------------------
# SUPABASE CONFIG
# -------------------------
SUPABASE_URL = "https://dxychuozluaxfmpehshj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4eWNodW96bHVheGZtcGVoc2hqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU5NzU4NzEsImV4cCI6MjA5MTU1MTg3MX0.ZXgrwkHFL50ec4nDHfusMFgWBKYM4MsvX9Owc8wWeVU"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------
# SESSION STATE
# -------------------------
if "msg" not in st.session_state:
    st.session_state.msg = ""

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

# -------------------------
# FORMAT
# -------------------------
def format_currency(x):
    if x >= 1_000_000:
        return f"{x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"{x/1_000:.2f}K"
    return f"{x:.2f}"

# -------------------------
# LOAD DATA
# -------------------------
def load_expenses():
    response = supabase.table("expenses").select("*").order("date", desc=True).execute()
    data = response.data

    if not data:
        return pd.DataFrame(columns=["ID", "Date", "Category", "Amount", "Description"])

    df = pd.DataFrame(data)

    df["Date"] = pd.to_datetime(df["date"]).dt.date
    df["Category"] = df["category"].astype(str).str.title()
    df["Amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["Description"] = df.get("description", "")

    df = df.sort_values("Date", ascending=False).reset_index(drop=True)
    df["ID"] = df["id"]

    return df[["ID", "Date", "Category", "Amount", "Description"]]

# -------------------------
# ADD
# -------------------------
def add_expense(row):
    supabase.table("expenses").insert({
        "date": row["Date"].strftime("%Y-%m-%d"),
        "category": row["Category"].lower(),
        "amount": float(row["Amount"]),
        "description": row["Description"]
    }).execute()

# -------------------------
# UPDATE
# -------------------------
def update_expense(row):
    supabase.table("expenses").update({
        "date": row["Date"].strftime("%Y-%m-%d"),
        "category": row["Category"].lower(),
        "amount": float(row["Amount"]),
        "description": row["Description"]
    }).eq("id", int(row["ID"])).execute()

# -------------------------
# DELETE
# -------------------------
def delete_expense(id_):
    supabase.table("expenses").delete().eq("id", int(id_)).execute()

# -------------------------
# LOAD INIT DATA
# -------------------------
if "df_expenses" not in st.session_state:
    st.session_state.df_expenses = load_expenses()

df = st.session_state.df_expenses

# -------------------------
# MESSAGE
# -------------------------
if st.session_state.msg:
    st.toast(st.session_state.msg, icon="✅")
    st.session_state.msg = ""

# -------------------------
# SIDEBAR
# -------------------------
st.sidebar.title("Menu")

if st.sidebar.button("Dashboard"):
    st.session_state.page = "Dashboard"
if st.sidebar.button("Add Expense"):
    st.session_state.page = "Add"
if st.sidebar.button("Update Expense"):
    st.session_state.page = "Update"
if st.sidebar.button("Delete Expense"):
    st.session_state.page = "Delete"
if st.sidebar.button("View Data"):
    st.session_state.page = "View"

# -------------------------
# DASHBOARD
# -------------------------
if st.session_state.page == "Dashboard":
    st.title("📊 Financial Insights")

    if not df.empty:

        date_calc = pd.to_datetime(df["Date"])

        total = df["Amount"].sum()

        today = date.today()
        monthly = df[
            (date_calc.dt.month == today.month) &
            (date_calc.dt.year == today.year)
        ]["Amount"].sum()

        avg = df["Amount"].mean()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Spending", format_currency(total))
        col2.metric("This Month", format_currency(monthly))
        col3.metric("Avg. Transaction", format_currency(avg))

        st.markdown("---")

        col_left, col_right = st.columns(2)
        cat = df.groupby("Category")["Amount"].sum().reset_index()

        with col_left:
            st.subheader("Category Totals")
            st.plotly_chart(
                px.bar(cat, x="Amount", y="Category", orientation="h",
                       color="Amount", color_continuous_scale="Teal",
                       template="plotly_white"),
                use_container_width=True
            )

        with col_right:
            st.subheader("Spending Split")
            st.plotly_chart(
                px.pie(cat, values="Amount", names="Category",
                       hole=0.4,
                       color_discrete_sequence=px.colors.sequential.Purp_r),
                use_container_width=True
            )

        st.subheader("Spending Trend (Monthly)")

        temp = df.copy()
        temp["date_calc"] = pd.to_datetime(temp["Date"])

        temp["month_sort"] = temp["date_calc"].dt.to_period("M")
        temp["Month"] = temp["date_calc"].dt.strftime("%b %y")

        monthly_trend = temp.groupby(["month_sort", "Month"], as_index=False)["Amount"].sum()
        monthly_trend = monthly_trend.sort_values("month_sort")

        st.plotly_chart(
            px.area(
                monthly_trend,
                x="Month",
                y="Amount",
                color_discrete_sequence=["#008080"],
                template="plotly_white"
            ),
            use_container_width=True
        )

        st.subheader("Recent Expenses")

        recent = df.copy()
        recent["Date"] = pd.to_datetime(recent["Date"]).dt.strftime("%d/%m/%Y")

        st.dataframe(
            recent.sort_values("Date", ascending=False)
            .head(5)[["Date", "Category", "Amount", "Description"]],
            use_container_width=True,
            hide_index=True
        )

    else:
        st.warning("No data available. Add some expenses!")

# -------------------------
# ADD
# -------------------------
elif st.session_state.page == "Add":
    st.title("➕ Add Expense")

    categories = sorted(df["Category"].dropna().unique().tolist())
    cat = st.selectbox("Category", categories + ["Other"])

    if cat == "Other":
        cat = st.text_input("Enter Category")

    amount = st.number_input("Amount", min_value=0.0)
    dt = st.date_input("Date", date.today())
    desc = st.text_input("Description")

    if st.button("Add"):
        if cat and amount > 0:
            add_expense({
                "Date": dt,
                "Category": cat,
                "Amount": amount,
                "Description": desc
            })

            st.session_state.df_expenses = load_expenses()
            st.session_state.msg = "Expense Added"
            st.rerun()

# -------------------------
# UPDATE (FIXED DATE FORMAT)
# -------------------------
elif st.session_state.page == "Update":
    st.title("✏️ Update Expense")

    view_df = df.copy()
    view_df["Date"] = pd.to_datetime(view_df["Date"]).dt.strftime("%d/%m/%Y")
    st.dataframe(view_df, use_container_width=True)

    id_ = st.number_input("Enter ID", min_value=1)

    if id_ in df["ID"].values:
        row = df[df["ID"] == id_].iloc[0]

        cat = st.text_input("Category", row["Category"])
        amt = st.number_input("Amount", value=float(row["Amount"]))
        dt = st.date_input("Date", row["Date"])
        desc = st.text_input("Description", row["Description"])

        if st.button("Update"):
            update_expense({
                "ID": id_,
                "Date": dt,
                "Category": cat,
                "Amount": amt,
                "Description": desc
            })

            st.session_state.df_expenses = load_expenses()
            st.session_state.msg = "Updated"
            st.rerun()

# -------------------------
# DELETE (FIXED DATE FORMAT)
# -------------------------
elif st.session_state.page == "Delete":
    st.title("🗑️ Delete Expense")

    view_df = df.copy()
    view_df["Date"] = pd.to_datetime(view_df["Date"]).dt.strftime("%d/%m/%Y")
    st.dataframe(view_df, use_container_width=True)

    id_ = st.number_input("Enter ID", min_value=1)

    if st.button("Delete"):
        if id_ in df["ID"].values:
            delete_expense(id_)

            st.session_state.df_expenses = load_expenses()
            st.session_state.msg = "Deleted"
            st.rerun()

# -------------------------
# VIEW
# -------------------------
elif st.session_state.page == "View":
    st.title("📄 All Data")

    view = df.copy()
    view["Date"] = pd.to_datetime(view["Date"]).dt.strftime("%d/%m/%Y")

    st.dataframe(view, use_container_width=True)