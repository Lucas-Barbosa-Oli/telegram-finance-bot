"""Hub runner — lists all available MCP servers and their registered tools.

Usage (from the mcp-hub directory):
    python -m servers
"""

from servers.finance.server import TOOL_REGISTRY as FINANCE_TOOLS, mcp_server as finance_server
from servers.core.server import TOOL_REGISTRY as CORE_TOOLS, mcp_server as core_server

_SERVERS = [
    ("finance", finance_server, FINANCE_TOOLS),
    ("core", core_server, CORE_TOOLS),
]


def _list_servers() -> None:
    print("MCP Hub — available servers\n" + "=" * 40)
    for name, server, registry in _SERVERS:
        print(f"\n[{name}]  (FastMCP server: \"{server.name}\")")
        print(f"  Run:   python -m servers.{name}")
        print(f"  Tools ({len(registry)}):")
        for tool_name in registry:
            print(f"    - {tool_name}")
    print()


if __name__ == "__main__":
    _list_servers()
