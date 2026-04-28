from typing import Any, Dict
import httpx
from shared.errors import ok, fail


def http_fetch_json(url: str, timeout_seconds: int = 15) -> Dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url)
            response.raise_for_status()
            return ok(response.json())
    except Exception as exc:
        return fail("HTTP_FETCH_JSON_FAILED", "Falha ao consultar URL.", str(exc))
