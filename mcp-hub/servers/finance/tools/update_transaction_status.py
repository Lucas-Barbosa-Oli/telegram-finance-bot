from typing import Any, Dict
from shared.errors import ok, fail
from shared.supabase_client import get_supabase_client


def update_transaction_status(user_id: int, transaction_id: int, status: str) -> Dict[str, Any]:
    client = get_supabase_client()
    if client is None:
        return fail("SUPABASE_NOT_CONFIGURED", "Defina SUPABASE_URL e SUPABASE_KEY.")

    if status not in {"planned", "confirmed"}:
        return fail("INVALID_STATUS", "Status invalido. Use 'planned' ou 'confirmed'.")

    try:
        response = (
            client.table("transactions")
            .update({"status": status})
            .eq("id", transaction_id)
            .eq("user_id", user_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return fail("TRANSACTION_NOT_FOUND", "Lancamento nao encontrado para este usuario.")

        return ok(rows[0])
    except Exception as exc:
        return fail("UPDATE_TRANSACTION_STATUS_FAILED", "Falha ao atualizar status do lancamento.", str(exc))
