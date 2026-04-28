from typing import Any, Dict
from datetime import datetime, timezone
from shared.errors import ok


def health_check() -> Dict[str, Any]:
    return ok({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()})
