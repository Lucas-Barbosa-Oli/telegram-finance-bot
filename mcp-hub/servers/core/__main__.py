"""Entry point for running the core MCP server as a module.

Usage (from the mcp-hub directory):
    python -m servers.core
"""

from servers.core.server import mcp_server

mcp_server.run()
