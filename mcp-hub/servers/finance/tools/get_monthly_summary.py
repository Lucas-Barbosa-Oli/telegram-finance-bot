from typing import Any, Dict
from datetime import datetime
import calendar
from shared.errors import ok, fail
from shared.supabase_client import get_supabase_client


def get_monthly_summary(user_id: int, month: int, year: int, include_planned: bool = False) -> Dict[str, Any]:
    client = get_supabase_client()
    if client is None:
        return fail("SUPABASE_NOT_CONFIGURED", "Defina SUPABASE_URL e SUPABASE_KEY.")

    try:
        start_date = datetime(year, month, 1).isoformat()
        end_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, end_day, 23, 59, 59).isoformat()

        query = (
            client.table("transactions")
            .select("*")
            .eq("user_id", user_id)
            .gte("created_at", start_date)
            .lte("created_at", end_date)
        )
        if not include_planned:
            query = query.eq("status", "confirmed")

        response = query.execute()

        rows = response.data or []
        total_income = sum(float(item["amount"]) for item in rows if item.get("type") == "income")
        total_expense = sum(float(item["amount"]) for item in rows if item.get("type") == "expense")
        balance = total_income - total_expense

        planned_income = 0.0
        planned_expense = 0.0
        if not include_planned:
            planned_response = (
                client.table("transactions")
                .select("amount,type")
                .eq("user_id", user_id)
                .eq("status", "planned")
                .gte("created_at", start_date)
                .lte("created_at", end_date)
                .execute()
            )
            planned_rows = planned_response.data or []
            planned_income = sum(float(item["amount"]) for item in planned_rows if item.get("type") == "income")
            planned_expense = sum(float(item["amount"]) for item in planned_rows if item.get("type") == "expense")

        return ok(
            {
                "month": month,
                "year": year,
                "total_income": total_income,
                "total_expense": total_expense,
                "balance": balance,
                "transactions_count": len(rows),
                "transactions": rows,
                "planned_income": planned_income,
                "planned_expense": planned_expense,
                "planned_balance": planned_income - planned_expense,
            }
        )
    except Exception as exc:
        return fail("GET_MONTHLY_SUMMARY_FAILED", "Falha ao consultar resumo mensal.", str(exc))
