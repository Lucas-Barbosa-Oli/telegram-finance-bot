from typing import Any, Dict
from shared.errors import ok, fail
from shared.supabase_client import get_supabase_client


def delete_transaction(user_id: int, transaction_id: int) -> Dict[str, Any]:
    client = get_supabase_client()
    if client is None:
        return fail("SUPABASE_NOT_CONFIGURED", "Defina SUPABASE_URL e SUPABASE_KEY.")

    try:
        fetch_response = (
            client.table("transactions")
            .select("*")
            .eq("id", transaction_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = fetch_response.data or []
        if not rows:
            return fail("TRANSACTION_NOT_FOUND", "Lancamento nao encontrado para este usuario.")

        deleted = rows[0]
        (
            client.table("transactions")
            .delete()
            .eq("id", transaction_id)
            .eq("user_id", user_id)
            .execute()
        )
        return ok(deleted)
    except Exception as exc:
        return fail("DELETE_TRANSACTION_FAILED", "Falha ao cancelar lancamento.", str(exc))
