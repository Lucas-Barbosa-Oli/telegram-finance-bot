"""Entry point for running the finance MCP server as a module.

Usage (from the mcp-hub directory):
    python -m servers.finance
"""

from servers.finance.server import mcp_server

mcp_server.run()
