import streamlit as st
import pandas as pd
import plotly.express as px
from utils.supabase_client import fetch_all_expenses

st.set_page_config(page_title="Analytics | FinSight AI", page_icon="📈", layout="wide")
st.title("📈 Spending Analytics")

raw_data = fetch_all_expenses()

if not raw_data:
    st.info("No expense data available to analyze.")
else:
    df = pd.DataFrame(raw_data)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])

    # Filters
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        selected_categories = st.multiselect(
            "Filter by Category",
            options=df["category"].unique().tolist(),
            default=df["category"].unique().tolist()
        )
    with col_filter2:
        date_range = st.date_input(
            "Select Date Range",
            value=[df["date"].min().date(), df["date"].max().date()]
        )

    # Filter application
    filtered_df = df[df["category"].isin(selected_categories)]
    if len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df["date"].dt.date >= date_range[0]) & 
            (filtered_df["date"].dt.date <= date_range[1])
        ]

    st.divider()

    # Visualizations
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Category Breakdown")
        cat_summary = filtered_df.groupby("category")["amount"].sum().reset_index()
        fig_pie = px.pie(
            cat_summary, 
            values="amount", 
            names="category", 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.subheader("Spending by Category")
        fig_bar = px.bar(
            cat_summary.sort_values(by="amount", ascending=False),
            x="category",
            y="amount",
            labels={"amount": "Amount (₹)", "category": "Category"},
            color="category",
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Spending Over Time")
    daily_spend = filtered_df.groupby("date")["amount"].sum().reset_index().sort_values(by="date")
    fig_line = px.area(
        daily_spend,
        x="date",
        y="amount",
        labels={"amount": "Daily Spend (₹)", "date": "Date"},
        line_shape="spline"
    )
    st.plotly_chart(fig_line, use_container_width=True)