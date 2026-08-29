import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def fetch_all_expenses() -> list[dict]:
    supabase = get_supabase_client()
    response = supabase.table("expenses").select("*").order("date", desc=True).execute()
    return response.data or []

def insert_expenses_batch(records: list[dict]):
    supabase = get_supabase_client()
    return supabase.table("expenses").insert(records).execute()

def delete_expense_by_id(expense_id: int):
    supabase = get_supabase_client()
    return supabase.table("expenses").delete().eq("id", expense_id).execute()