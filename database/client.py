import os
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

if url and key:
    supabase: Optional[Client] = create_client(url, key)
else:
    supabase = None

async def add_transaction(user_id: int, amount: float, trans_type: str, category: str, description: str = ""):
    if supabase is None:
        raise RuntimeError("Supabase client is not configured. Set SUPABASE_URL and SUPABASE_KEY.")

    data = {
        "user_id": user_id,
        "amount": amount,
        "type": trans_type,
        "category": category,
        "description": description
    }
    response = supabase.table("transactions").insert(data).execute()
    return response.data

async def get_monthly_summary(user_id: int, month: int, year: int):
    if supabase is None:
        raise RuntimeError("Supabase client is not configured. Set SUPABASE_URL and SUPABASE_KEY.")

    import calendar
    from datetime import datetime
    
    # Calculate start and end of month
    start_date = datetime(year, month, 1).isoformat()
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59).isoformat()

    response = supabase.table("transactions") \
        .select("*") \
        .eq("user_id", user_id) \
        .gte("created_at", start_date) \
        .lte("created_at", end_date) \
        .execute()
    
    return response.data

async def get_recent_transactions(user_id: int, limit: int = 10):
    if supabase is None:
        raise RuntimeError("Supabase client is not configured. Set SUPABASE_URL and SUPABASE_KEY.")

    response = supabase.table("transactions") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    return response.data
