import json
import pandas as pd
from typing import List, Literal
from pydantic import BaseModel, Field
from groq import Groq
import streamlit as st

class ExpenseItem(BaseModel):
    date: str = Field(description="Transaction date strictly in YYYY-MM-DD format")
    category: Literal["Food", "Travel", "Bills", "Shopping", "Entertainment", "Health", "Other"] = Field(
        description="Standardized category assigned based on merchant, item name, or description"
    )
    amount: float = Field(description="Positive numerical cost of the transaction")
    description: str = Field(description="Concise description or merchant name")

class ExtractedExpensePayload(BaseModel):
    transactions: List[ExpenseItem]

def parse_spreadsheet_with_agent(df: pd.DataFrame) -> list[dict]:
    # Clean and strip any accidental whitespace, quotes, or trailing newlines
    raw_key = st.secrets.get("GROQ_API_KEY", "")
    api_key = str(raw_key).strip().strip('"').strip("'")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing or empty in secrets.")

    client = Groq(api_key=api_key)
    
    # Convert first 150 rows of user spreadsheet to CSV text
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

    # Priority list of models to try in order
    candidate_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b"
    ]

    last_error = None
    for model_name in candidate_models:
        try:
            completion = client.chat.completions.create(
                model=model_name,
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
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"All candidate models failed. Last error: {str(last_error)}")