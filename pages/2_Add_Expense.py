import streamlit as st
import pandas as pd
from datetime import date
from utils.supabase_client import insert_expenses_batch
from utils.excel_agent import parse_spreadsheet_with_agent

st.set_page_config(page_title="Add Expense | FinSight AI", page_icon="➕", layout="wide")
st.title("➕ Add Expenses")

tab1, tab2 = st.tabs(["📝 Manual Entry", "🤖 Bulk Upload via AI Agent"])

with tab1:
    st.subheader("Manual Transaction Entry")
    with st.form("manual_expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tx_date = st.date_input("Date", value=date.today())
            category = st.selectbox(
                "Category",
                ["Food", "Travel", "Bills", "Shopping", "Entertainment", "Health", "Other"]
            )
        with col2:
            amount = st.number_input("Amount (₹)", min_value=0.01, step=1.0, format="%.2f")
            description = st.text_input("Description / Merchant")

        submitted = st.form_submit_button("Save Expense")
        if submitted:
            if not description.strip():
                st.error("Please provide a description.")
            else:
                record = {
                    "date": tx_date.strftime("%Y-%m-%d"),
                    "category": category,
                    "amount": float(amount),
                    "description": description.strip()
                }
                insert_expenses_batch([record])
                st.success("Expense saved to Supabase successfully!")

with tab2:
    st.subheader("Intelligent Spreadsheet Extraction")
    st.markdown("Upload any bank statement or raw spreadsheet (`.xlsx`, `.csv`). The AI agent will extract, normalize, and categorize the entries.")

    uploaded_file = st.file_uploader("Upload File", type=["xlsx", "csv"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".xlsx"):
                raw_df = pd.read_excel(uploaded_file)
            else:
                raw_df = pd.read_csv(uploaded_file)
            
            st.write("Uploaded File Preview (First 5 rows):")
            st.dataframe(raw_df.head(5), use_container_width=True)

            if st.button("Run AI Agent Extraction"):
                with st.spinner("AI Agent analyzing schema, standardizing dates, and assigning categories..."):
                    extracted_records = parse_spreadsheet_with_agent(raw_df)
                    st.session_state["staging_expenses"] = extracted_records
                    st.success(f"Successfully processed {len(extracted_records)} records!")
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")

    if "staging_expenses" in st.session_state and st.session_state["staging_expenses"]:
        st.divider()
        st.subheader("Review & Edit Extracted Transactions")
        st.caption("Verify the extracted fields before committing them to the database.")

        staged_df = pd.DataFrame(st.session_state["staging_expenses"])
        
        # Interactive editor for human-in-the-loop review
        edited_df = st.data_editor(
            staged_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
                "category": st.column_config.SelectboxColumn(
                    "Category",
                    options=["Food", "Travel", "Bills", "Shopping", "Entertainment", "Health", "Other"]
                ),
                "amount": st.column_config.NumberColumn("Amount", format="₹%.2f"),
                "description": st.column_config.TextColumn("Description")
            }
        )

        # In your Add Expense / Ingestion page:
        if st.button("Confirm & Insert All Records"):
            # Ensure all rows from the staged dataframe/editor are converted:
            records_to_insert = staged_df.to_dict(orient="records")
            
            # Batch insert all records:
            insert_expenses_batch(records_to_insert)
            st.success(f"Successfully inserted {len(records_to_insert)} expenses!")
            st.rerun()