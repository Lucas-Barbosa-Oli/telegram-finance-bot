from typing import Any, Dict
from shared.errors import ok, fail
from shared.supabase_client import get_supabase_client


def create_transaction(user_id: int, amount: float, trans_type: str, category: str, description: str = "") -> Dict[str, Any]:
    client = get_supabase_client()
    if client is None:
        return fail("SUPABASE_NOT_CONFIGURED", "Defina SUPABASE_URL e SUPABASE_KEY.")

    try:
        payload = {
            "user_id": user_id,
            "amount": amount,
            "type": trans_type,
            "category": category,
            "description": description,
        }
        response = client.table("transactions").insert(payload).execute()
        return ok(response.data)
    except Exception as exc:
        return fail("CREATE_TRANSACTION_FAILED", "Falha ao criar transacao.", str(exc))
