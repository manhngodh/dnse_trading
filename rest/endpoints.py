"""
DNSE API endpoint definitions.
"""


def get_login_url(base_url: str) -> str:
    """Get login endpoint URL."""
    return f"{base_url}/auth-service/login"


def get_trading_token_url(base_url: str) -> str:
    """Get trading token (OTP verification) endpoint URL."""
    return f"{base_url}/order-service/trading-token"


def get_account_info_url(base_url: str) -> str:
    """Get account info endpoint URL."""
    return f"{base_url}/user-service/api/me"


def get_sub_accounts_url(base_url: str) -> str:
    """Get sub-accounts endpoint URL."""
    return f"{base_url}/user-service/api/accounts"


# ============================================================================
# Base Trading (Stocks)
# ============================================================================

def get_base_orders_url(base_url: str) -> str:
    """Get base orders endpoint URL for placing orders."""
    return f"{base_url}/order-service/v2/orders"


def get_base_order_detail_url(base_url: str, order_id: int) -> str:
    """Get base order detail endpoint URL."""
    return f"{base_url}/order-service/v2/orders/{order_id}"


def get_base_cancel_order_url(base_url: str, order_id: int, account_no: str) -> str:
    """Get base cancel order endpoint URL."""
    return f"{base_url}/order-service/v2/orders/{order_id}?accountNo={account_no}"


def get_base_loan_packages_url(base_url: str) -> str:
    """Get base loan packages endpoint URL."""
    return f"{base_url}/order-service/loan-packages"


def get_base_buying_power_url(base_url: str) -> str:
    """Get base buying power endpoint URL."""
    return f"{base_url}/order-service/pp"


def get_base_holdings_url(base_url: str) -> str:
    """Get base holdings endpoint URL."""
    return f"{base_url}/order-service/holdings"


# ============================================================================
# Derivative Trading
# ============================================================================

def get_derivative_orders_url(base_url: str) -> str:
    """Get derivative orders endpoint URL for placing orders."""
    return f"{base_url}/order-service/derivative/orders"


def get_derivative_order_detail_url(base_url: str, order_id: int) -> str:
    """Get derivative order detail endpoint URL."""
    return f"{base_url}/order-service/derivative/orders/{order_id}"


def get_derivative_cancel_order_url(base_url: str, order_id: int, account_no: str) -> str:
    """Get derivative cancel order endpoint URL."""
    return f"{base_url}/order-service/derivative/orders/{order_id}?accountNo={account_no}"


def get_derivative_loan_packages_url(base_url: str) -> str:
    """Get derivative loan packages endpoint URL."""
    return f"{base_url}/order-service/derivative/loan-packages"


def get_derivative_buying_power_url(base_url: str) -> str:
    """Get derivative buying power endpoint URL."""
    return f"{base_url}/order-service/derivative/pp"


def get_derivative_positions_url(base_url: str) -> str:
    """Get derivative positions endpoint URL."""
    return f"{base_url}/order-service/derivative/positions"


def get_derivative_assets_url(base_url: str) -> str:
    """Get derivative assets endpoint URL."""
    return f"{base_url}/order-service/derivative/assets"
