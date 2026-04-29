from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from servers.finance.tools.create_transaction import create_transaction as create_transaction_tool
from servers.finance.tools.get_recent_transactions import get_recent_transactions as get_recent_transactions_tool
from servers.finance.tools.get_monthly_summary import get_monthly_summary as get_monthly_summary_tool
from servers.finance.tools.get_category_breakdown import get_category_breakdown as get_category_breakdown_tool

# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp_server = FastMCP("finance")

# ---------------------------------------------------------------------------
# Tool registrations — thin wrappers that delegate to the plain tool functions
# ---------------------------------------------------------------------------


@mcp_server.tool()
def create_transaction(
    user_id: int,
    amount: float,
    trans_type: str,
    category: str,
    description: str = "",
) -> Dict[str, Any]:
    """Create a new financial transaction for a user.

    Args:
        user_id: Telegram user ID.
        amount: Transaction amount (positive number).
        trans_type: Either "income" or "expense".
        category: Transaction category label.
        description: Optional free-text description.
    """
    return create_transaction_tool(user_id, amount, trans_type, category, description)


@mcp_server.tool()
def get_recent_transactions(
    user_id: int,
    limit: int = 15,
) -> Dict[str, Any]:
    """Return the most recent transactions for a user.

    Args:
        user_id: Telegram user ID.
        limit: Maximum number of records to return (default 15).
    """
    return get_recent_transactions_tool(user_id, limit)


@mcp_server.tool()
def get_monthly_summary(
    user_id: int,
    month: int,
    year: int,
) -> Dict[str, Any]:
    """Return a monthly income/expense summary for a user.

    Args:
        user_id: Telegram user ID.
        month: Month number (1-12).
        year: Four-digit year.
    """
    return get_monthly_summary_tool(user_id, month, year)


@mcp_server.tool()
def get_category_breakdown(
    user_id: int,
    month: int,
    year: int,
) -> Dict[str, Any]:
    """Return expense totals grouped by category for a given month.

    Args:
        user_id: Telegram user ID.
        month: Month number (1-12).
        year: Four-digit year.
    """
    return get_category_breakdown_tool(user_id, month, year)


# ---------------------------------------------------------------------------
# Backward-compatible registry (used by code that imports TOOL_REGISTRY)
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "create_transaction": create_transaction_tool,
    "get_recent_transactions": get_recent_transactions_tool,
    "get_monthly_summary": get_monthly_summary_tool,
    "get_category_breakdown": get_category_breakdown_tool,
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp_server.run()
