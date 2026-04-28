from servers.core.tools.health_check import health_check
from servers.core.tools.http_fetch_json import http_fetch_json


TOOL_REGISTRY = {
    "health_check": health_check,
    "http_fetch_json": http_fetch_json,
}
