from typing import Any, Dict
from shared.errors import ok, fail
from shared.supabase_client import get_supabase_client


def get_recent_transactions(user_id: int, limit: int = 15) -> Dict[str, Any]:
    client = get_supabase_client()
    if client is None:
        return fail("SUPABASE_NOT_CONFIGURED", "Defina SUPABASE_URL e SUPABASE_KEY.")

    try:
        response = (
            client.table("transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return ok(response.data)
    except Exception as exc:
        return fail("GET_RECENT_TRANSACTIONS_FAILED", "Falha ao consultar extrato recente.", str(exc))
