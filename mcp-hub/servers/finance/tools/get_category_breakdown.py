from typing import Any, Dict
from datetime import datetime
import calendar
from shared.errors import ok, fail
from shared.supabase_client import get_supabase_client


def get_category_breakdown(user_id: int, month: int, year: int) -> Dict[str, Any]:
    client = get_supabase_client()
    if client is None:
        return fail("SUPABASE_NOT_CONFIGURED", "Defina SUPABASE_URL e SUPABASE_KEY.")

    try:
        start_date = datetime(year, month, 1).isoformat()
        end_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, end_day, 23, 59, 59).isoformat()

        response = (
            client.table("transactions")
            .select("category,amount,type")
            .eq("user_id", user_id)
            .eq("type", "expense")
            .gte("created_at", start_date)
            .lte("created_at", end_date)
            .execute()
        )

        rows = response.data or []
        totals: Dict[str, float] = {}
        for item in rows:
            category = item.get("category") or "sem categoria"
            totals[category] = totals.get(category, 0.0) + float(item.get("amount") or 0.0)

        breakdown = [{"category": k, "amount": v} for k, v in sorted(totals.items(), key=lambda x: x[1], reverse=True)]
        return ok({"month": month, "year": year, "breakdown": breakdown})
    except Exception as exc:
        return fail("GET_CATEGORY_BREAKDOWN_FAILED", "Falha ao consultar categorias.", str(exc))
