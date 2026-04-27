import asyncio
import os
from database.client import add_transaction, get_monthly_summary
import datetime

async def test_db():
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
        print("Supabase credentials missing. Skipping DB test.")
        return

    user_id = 999999
    now = datetime.datetime.now()
    
    print(f"Adding test transaction for user {user_id}...")
    try:
        await add_transaction(user_id, 100.0, "expense", "Teste", "Compra de teste")
        print("Transaction added!")
        
        summary = await get_monthly_summary(user_id, now.month, now.year)
        print(f"Summary retrieved: {len(summary)} items found.")
    except Exception as e:
        print(f"DB Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
