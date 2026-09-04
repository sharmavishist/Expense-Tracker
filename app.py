import json
import streamlit as st
import pandas as pd
from datetime import date
import plotly.express as px
from typing import List, Literal
from pydantic import BaseModel, Field
from supabase import create_client, Client
from groq import Groq

st.set_page_config(page_title="Expense Tracker | FinSight AI", page_icon="💰", layout="wide")

# -------------------------
# SUPABASE & SECRETS CONFIG
# -------------------------
try:
    SUPABASE_URL = st.secrets["https://dxychuozluaxfmpehshj.supabase.com"]
    SUPABASE_KEY = st.secrets["sb_publishable_pw_nlDvKTDJHsJ6PxdKO3w_NAPXIEy8"]
except KeyError:
    # Fallback to defaults if secrets.toml is missing
    SUPABASE_URL = "https://dxychuozluaxfmpehshj.supabase.com"
    SUPABASE_KEY = "sb_publishable_pw_nlDvKTDJHsJ6PxdKO3w_NAPXIEy8"

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

# -------------------------
# AI AGENT SCHEMAS & HELPERS
# -------------------------
class ExpenseItem(BaseModel):
    date: str = Field(description="Transaction date strictly in YYYY-MM-DD format")
    category: Literal["Food", "Travel", "Bills", "Shopping", "Entertainment", "Health", "Other"] = Field(
        description="Standardized category assigned based on merchant, item name, or description"
    )
    amount: float = Field(description="Positive numerical cost of the transaction")
    description: str = Field(description="Concise description or merchant name")

class ExtractedExpensePayload(BaseModel):
    transactions: List[ExpenseItem]

def get_best_available_model(client: Groq) -> str:
    """Dynamically fetches active models from Groq account."""
    try:
        available_models = [m.id for m in client.models.list().data]
        preferred_order = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
        for pref in preferred_order:
            if pref in available_models:
                return pref
        return available_models[0] if available_models else "llama3-8b-8192"
    except Exception:
        return "llama3-8b-8192"

def parse_spreadsheet_with_agent(df: pd.DataFrame) -> list[dict]:
    raw_key = st.secrets.get("GROQ_API_KEY", "")
    api_key = str(raw_key).strip().strip('"').strip("'")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing or empty in secrets. Please set it in .streamlit/secrets.toml.")

    client = Groq(api_key=api_key)
    selected_model = get_best_available_model(client)
    
    csv_sample = df.head(150).to_csv(index=False)
    schema_json = json.dumps(ExtractedExpensePayload.model_json_schema(), indent=2)

    system_prompt = f"""
You are an expert financial ingestion AI.
Analyze the raw tabular financial statement data provided by the user.

Tasks:
1. Map raw columns corresponding to transaction date, amount/debit, description/merchant/notes, and category.
2. Convert all dates strictly to standard 'YYYY-MM-DD' format.
3. Ensure all amounts are positive float values.
4. Categorize each item into exactly one of: ['Food', 'Travel', 'Bills', 'Shopping', 'Entertainment', 'Health', 'Other'].
5. Standardize messy descriptions and remove unnecessary prefixes.

You MUST respond strictly with a valid JSON object matching this schema:
{schema_json}
"""
    user_prompt = f"Raw Statement Data:\n{csv_sample}"

    completion = client.chat.completions.create(
        model=selected_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    raw_response = completion.choices[0].message.content
    parsed = json.loads(raw_response)
    
    if isinstance(parsed, dict):
        if "transactions" in parsed and isinstance(parsed["transactions"], list):
            return parsed["transactions"]
        for val in parsed.values():
            if isinstance(val, list):
                return val
    elif isinstance(parsed, list):
        return parsed

    return []

# -------------------------
# SESSION STATE & HELPERS
# -------------------------
if "msg" not in st.session_state:
    st.session_state.msg = ""

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

def format_currency(x):
    if x >= 1_000_000:
        return f"₹{x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"₹{x/1_000:.2f}K"
    return f"₹{x:.2f}"

def load_expenses():
    response = supabase.table("expenses").select("*").order("date", desc=True).execute()
    data = response.data

    if not data:
        return pd.DataFrame(columns=["ID", "Date", "Category", "Amount", "Description"])

    df = pd.DataFrame(data)
    df["Date"] = pd.to_datetime(df["date"]).dt.date
    df["Category"] = df["category"].astype(str).str.title()
    df["Amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["Description"] = df.get("description", "")
    df["ID"] = df["id"]

    df = df.sort_values("Date", ascending=False).reset_index(drop=True)
    return df[["ID", "Date", "Category", "Amount", "Description"]]

def add_expense(row):
    supabase.table("expenses").insert({
        "date": row["Date"].strftime("%Y-%m-%d"),
        "category": row["Category"].lower(),
        "amount": float(row["Amount"]),
        "description": row["Description"]
    }).execute()

def insert_expenses_batch(records: list[dict]):
    supabase.table("expenses").insert(records).execute()

def update_expense(row):
    supabase.table("expenses").update({
        "date": row["Date"].strftime("%Y-%m-%d"),
        "category": row["Category"].lower(),
        "amount": float(row["Amount"]),
        "description": row["Description"]
    }).eq("id", int(row["ID"])).execute()

def delete_expense(id_):
    supabase.table("expenses").delete().eq("id", int(id_)).execute()

# Initialize state dataframe
if "df_expenses" not in st.session_state:
    st.session_state.df_expenses = load_expenses()

df = st.session_state.df_expenses

if st.session_state.msg:
    st.toast(st.session_state.msg, icon="✅")
    st.session_state.msg = ""

# -------------------------
# SIDEBAR
# -------------------------
st.sidebar.title("💳 FinSight AI")
st.sidebar.markdown("---")

if st.sidebar.button("📊 Dashboard", use_container_width=True):
    st.session_state.page = "Dashboard"
if st.sidebar.button("➕ Add Expense", use_container_width=True):
    st.session_state.page = "Add"
if st.sidebar.button("✏️ Update Expense", use_container_width=True):
    st.session_state.page = "Update"
if st.sidebar.button("🗑️ Delete Expense", use_container_width=True):
    st.session_state.page = "Delete"
if st.sidebar.button("📄 View All Data", use_container_width=True):
    st.session_state.page = "View"

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Force Refresh Data", use_container_width=True):
    st.session_state.df_expenses = load_expenses()
    st.session_state.msg = "Database refreshed!"
    st.rerun()

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
        recent = df.sort_values(by="Date", ascending=False).copy()
        recent["Display_Date"] = pd.to_datetime(recent["Date"]).dt.strftime("%d/%m/%Y")

        st.dataframe(
            recent[["Display_Date", "Category", "Amount", "Description"]].rename(columns={"Display_Date": "Date"}),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("No data available. Add some expenses to get started!")

# -------------------------
# ADD (MANUAL + AI AGENT BULK)
# -------------------------
elif st.session_state.page == "Add":
    st.title("➕ Add Expense")
    
    tab_manual, tab_agent = st.tabs(["✍️ Manual Single Entry", "🤖 Bulk Upload via AI Agent"])

    with tab_manual:
        existing_cats = sorted(df["Category"].dropna().unique().tolist())
        cat_options = existing_cats if existing_cats else ["Food", "Travel", "Bills", "Shopping", "Entertainment", "Health"]
        
        cat = st.selectbox("Category", cat_options + ["Other"])
        if cat == "Other":
            cat = st.text_input("Enter Custom Category")

        amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0)
        dt = st.date_input("Date", date.today())
        desc = st.text_input("Description / Notes")

        if st.button("Add Expense Record", type="primary"):
            if cat and amount > 0:
                add_expense({
                    "Date": dt,
                    "Category": cat,
                    "Amount": amount,
                    "Description": desc
                })
                st.session_state.df_expenses = load_expenses()
                st.session_state.msg = "Expense successfully added!"
                st.rerun()
            else:
                st.error("Please enter a valid category and amount greater than 0.")

    with tab_agent:
        st.subheader("Upload CSV or Excel Statement")
        st.caption("The Groq AI agent will parse messy column headers, reformat dates, and infer categories automatically.")
        
        uploaded_file = st.file_uploader("Choose a .csv or .xlsx file", type=["csv", "xlsx"])

        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_file)
                else:
                    raw_df = pd.read_excel(uploaded_file)

                st.write("**File Preview (First 5 rows):**")
                st.dataframe(raw_df.head(5), use_container_width=True)

                if st.button("🚀 Run AI Agent Extraction", type="primary"):
                    with st.spinner("AI is analyzing, normalizing, and categorizing transactions..."):
                        extracted_records = parse_spreadsheet_with_agent(raw_df)
                        if extracted_records:
                            st.session_state["staged_expenses"] = extracted_records
                            st.success(f"Successfully extracted {len(extracted_records)} transactions!")
                        else:
                            st.warning("No transactions could be parsed from the file.")
            except Exception as e:
                st.error(f"Error loading file: {str(e)}")

        if "staged_expenses" in st.session_state and st.session_state["staged_expenses"]:
            st.divider()
            st.subheader("Review Staged Transactions")
            staged_df = pd.DataFrame(st.session_state["staged_expenses"])
            
            edited_df = st.data_editor(
                staged_df,
                use_container_width=True,
                num_rows="dynamic",
                key="staged_editor"
            )

            col_commit, col_cancel = st.columns([0.3, 0.7])
            with col_commit:
                if st.button("💾 Confirm & Insert All Records", type="primary"):
                    with st.spinner("Inserting into Supabase..."):
                        final_records = edited_df.to_dict(orient="records")
                        # Format payload to match table fields
                        payload = [
                            {
                                "date": r["date"],
                                "category": str(r["category"]).lower(),
                                "amount": float(r["amount"]),
                                "description": str(r["description"])
                            }
                            for r in final_records
                        ]
                        insert_expenses_batch(payload)
                        st.session_state.df_expenses = load_expenses()
                        st.session_state["staged_expenses"] = []
                        st.session_state.msg = f"Successfully inserted {len(payload)} expenses!"
                        st.rerun()

            with col_cancel:
                if st.button("Clear Staging Table"):
                    st.session_state["staged_expenses"] = []
                    st.rerun()

# -------------------------
# UPDATE
# -------------------------
elif st.session_state.page == "Update":
    st.title("✏️ Update Expense")

    view_df = df.copy()
    view_df["Date"] = pd.to_datetime(view_df["Date"]).dt.strftime("%d/%m/%Y")
    st.dataframe(view_df, use_container_width=True, hide_index=True)

    id_ = st.number_input("Enter Transaction ID to Edit", min_value=1, step=1)

    if id_ in df["ID"].values:
        row = df[df["ID"] == id_].iloc[0]

        cat = st.text_input("Category", row["Category"])
        amt = st.number_input("Amount (₹)", value=float(row["Amount"]))
        dt = st.date_input("Date", row["Date"])
        desc = st.text_input("Description", row["Description"])

        if st.button("Update Record", type="primary"):
            update_expense({
                "ID": id_,
                "Date": dt,
                "Category": cat,
                "Amount": amt,
                "Description": desc
            })
            st.session_state.df_expenses = load_expenses()
            st.session_state.msg = f"Transaction ID #{id_} updated!"
            st.rerun()

# -------------------------
# DELETE
# -------------------------
elif st.session_state.page == "Delete":
    st.title("🗑️ Delete Expense")

    view_df = df.copy()
    view_df["Date"] = pd.to_datetime(view_df["Date"]).dt.strftime("%d/%m/%Y")
    st.dataframe(view_df, use_container_width=True, hide_index=True)

    id_ = st.number_input("Enter Transaction ID to Delete", min_value=1, step=1)

    if st.button("Delete Record", type="primary"):
        if id_ in df["ID"].values:
            delete_expense(id_)
            st.session_state.df_expenses = load_expenses()
            st.session_state.msg = f"Transaction ID #{id_} deleted!"
            st.rerun()
        else:
            st.error(f"Transaction ID #{id_} not found.")

# -------------------------
# VIEW ALL DATA
# -------------------------
elif st.session_state.page == "View":
    st.title("📄 Complete Expense Ledger")

    view = df.sort_values(by="Date", ascending=False).copy()
    view["Display_Date"] = pd.to_datetime(view["Date"]).dt.strftime("%d/%m/%Y")
    
    st.dataframe(
        view[["ID", "Display_Date", "Category", "Amount", "Description"]].rename(columns={"Display_Date": "Date"}),
        use_container_width=True,
        hide_index=True
    )