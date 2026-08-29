import json
import pandas as pd
from typing import List, Literal
from pydantic import BaseModel, Field
from groq import Groq
import streamlit as st

class ExpenseItem(BaseModel):
    date: str = Field(description="Transaction date strictly in YYYY-MM-DD format")
    category: Literal["Food", "Travel", "Bills", "Shopping", "Entertainment", "Health", "Other"] = Field(
        description="Standardized category assigned based on the merchant, description, or notes"
    )
    amount: float = Field(description="Positive numerical cost of the transaction")
    description: str = Field(description="Concise description or merchant name")

class ExtractedExpensePayload(BaseModel):
    transactions: List[ExpenseItem]

def parse_spreadsheet_with_agent(df: pd.DataFrame) -> list[dict]:
    # Initialize Groq client
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    
    # Take first 150 rows of user spreadsheet as CSV text
    csv_sample = df.head(150).to_csv(index=False)

    schema_json = json.dumps(ExtractedExpensePayload.model_json_schema(), indent=2)

    system_prompt = f"""
You are an expert financial ingestion AI.
Analyze the raw tabular financial statement data provided by the user.

Your tasks:
1. Map raw columns corresponding to date, amount, description/merchant, and category.
2. Convert all dates to standard 'YYYY-MM-DD' format.
3. Ensure all amounts are positive float values.
4. Categorize each item into exactly one of: ['Food', 'Travel', 'Bills', 'Shopping', 'Entertainment', 'Health', 'Other'].
5. Standardize messy descriptions.

You MUST respond strictly with a valid JSON object matching this schema:
{schema_json}
"""

    user_prompt = f"Raw Statement Data:\n{csv_sample}"

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    raw_response = completion.choices[0].message.content
    parsed = json.loads(raw_response)
    
    # Handle response regardless of root wrapping key
    if isinstance(parsed, dict):
        if "transactions" in parsed:
            return parsed["transactions"]
        for val in parsed.values():
            if isinstance(val, list):
                return val
    elif isinstance(parsed, list):
        return parsed

    return []