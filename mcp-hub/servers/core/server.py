from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from servers.core.tools.health_check import health_check as health_check_tool
from servers.core.tools.http_fetch_json import http_fetch_json as http_fetch_json_tool

# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp_server = FastMCP("core")

# ---------------------------------------------------------------------------
# Tool registrations — thin wrappers that delegate to the plain tool functions
# ---------------------------------------------------------------------------


@mcp_server.tool()
def health_check() -> Dict[str, Any]:
    """Return the current health status and UTC timestamp of the server."""
    return health_check_tool()


@mcp_server.tool()
def http_fetch_json(
    url: str,
    timeout_seconds: int = 15,
) -> Dict[str, Any]:
    """Fetch a URL and return its JSON payload.

    Args:
        url: The HTTP/HTTPS URL to retrieve.
        timeout_seconds: Request timeout in seconds (default 15).
    """
    return http_fetch_json_tool(url, timeout_seconds)


# ---------------------------------------------------------------------------
# Backward-compatible registry (used by code that imports TOOL_REGISTRY)
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "health_check": health_check_tool,
    "http_fetch_json": http_fetch_json_tool,
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp_server.run()
