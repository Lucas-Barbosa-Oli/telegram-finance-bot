from servers.finance.tools.create_transaction import create_transaction
from servers.finance.tools.get_recent_transactions import get_recent_transactions
from servers.finance.tools.get_monthly_summary import get_monthly_summary
from servers.finance.tools.get_category_breakdown import get_category_breakdown


TOOL_REGISTRY = {
    "create_transaction": create_transaction,
    "get_recent_transactions": get_recent_transactions,
    "get_monthly_summary": get_monthly_summary,
    "get_category_breakdown": get_category_breakdown,
}
