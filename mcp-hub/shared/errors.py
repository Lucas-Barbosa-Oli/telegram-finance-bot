from typing import Any, Dict


def ok(data: Any) -> Dict[str, Any]:
    return {"ok": True, "data": data}


def fail(code: str, message: str, details: Any = None) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }
