"""
Parsing utilities for DNSE order responses.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from adapters.dnse.common.types import (
    DNSEAccountInfo,
    DNSEBuyingPower,
    DNSEDerivativePosition,
    DNSEHolding,
    DNSELoanPackage,
    DNSEOrderResponse,
    DNSESubAccount,
)


def parse_account_info(data: dict) -> DNSEAccountInfo:
    """Parse account info from API response."""
    return DNSEAccountInfo(
        investor_id=data.get("investorId", ""),
        name=data.get("name", ""),
        custody_code=data.get("custodyCode", ""),
        mobile=data.get("mobile", ""),
        email=data.get("email", ""),
    )


def parse_sub_account(data: dict) -> DNSESubAccount:
    """Parse sub-account from API response."""
    return DNSESubAccount(
        account_no=data.get("accountNo", ""),
        account_type=data.get("accountType", "normal"),
        is_primary=data.get("isPrimary", False),
    )


def parse_loan_package(data: dict) -> DNSELoanPackage:
    """Parse loan package from API response."""
    return DNSELoanPackage(
        loan_package_id=data.get("id", 0),
        name=data.get("name", ""),
        initial_rate=Decimal(str(data.get("initialRate", 0))),
        maintenance_rate=Decimal(str(data.get("maintenanceRate", 0))),
        is_active=data.get("isActive", True),
    )


def parse_buying_power(data: dict) -> DNSEBuyingPower:
    """Parse buying power from API response."""
    return DNSEBuyingPower(
        account_no=data.get("accountNo", ""),
        symbol=data.get("symbol", ""),
        max_buy_qty=int(data.get("maxBuyQty", 0)),
        max_sell_qty=int(data.get("maxSellQty", 0)),
        available_cash=Decimal(str(data.get("availableCash", 0))),
    )


def parse_order_response(data: dict) -> DNSEOrderResponse:
    """Parse order response from API."""
    # Parse datetime fields
    created_date = _parse_datetime(data.get("createdDate"))
    modified_date = _parse_datetime(data.get("modifiedDate"))
    
    return DNSEOrderResponse(
        id=int(data.get("id", 0)),
        side=data.get("side", ""),
        account_no=data.get("accountNo", ""),
        investor_id=data.get("investorId", ""),
        symbol=data.get("symbol", ""),
        price=Decimal(str(data.get("price", 0))),
        quantity=int(data.get("quantity", 0)),
        order_type=data.get("orderType", ""),
        order_status=data.get("orderStatus", ""),
        fill_quantity=int(data.get("fillQuantity", 0)),
        last_quantity=int(data.get("lastQuantity", 0)),
        last_price=_parse_decimal(data.get("lastPrice")),
        average_price=_parse_decimal(data.get("averagePrice")),
        trans_date=data.get("transDate", ""),
        created_date=created_date or datetime.now(),
        modified_date=modified_date,
        tax_rate=_parse_decimal(data.get("taxRate")),
        fee_rate=_parse_decimal(data.get("feeRate")),
        leave_quantity=int(data.get("leaveQuantity", 0)),
        canceled_quantity=int(data.get("canceledQuantity", 0)),
        price_secure=_parse_decimal(data.get("priceSecure")),
        custody=data.get("custody", ""),
        channel=data.get("channel", ""),
        loan_package_id=data.get("loanPackageId"),
        initial_rate=_parse_decimal(data.get("initialRate")),
        error=data.get("error"),
    )


def parse_holding(data: dict) -> DNSEHolding:
    """Parse holding from API response."""
    return DNSEHolding(
        symbol=data.get("symbol", ""),
        quantity=int(data.get("quantity", 0)),
        available_quantity=int(data.get("availableQuantity", 0)),
        average_price=Decimal(str(data.get("averagePrice", 0))),
        market_price=Decimal(str(data.get("marketPrice", 0))),
        market_value=Decimal(str(data.get("marketValue", 0))),
        unrealized_pnl=Decimal(str(data.get("unrealizedPnl", 0))),
        unrealized_pnl_pct=Decimal(str(data.get("unrealizedPnlPct", 0))),
    )


def parse_derivative_position(data: dict) -> DNSEDerivativePosition:
    """Parse derivative position from API response."""
    return DNSEDerivativePosition(
        symbol=data.get("symbol", ""),
        side=data.get("side", ""),
        quantity=int(data.get("quantity", 0)),
        average_price=Decimal(str(data.get("averagePrice", 0))),
        market_price=Decimal(str(data.get("marketPrice", 0))),
        unrealized_pnl=Decimal(str(data.get("unrealizedPnl", 0))),
        initial_margin=Decimal(str(data.get("initialMargin", 0))),
        maintenance_margin=Decimal(str(data.get("maintenanceMargin", 0))),
    )


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse datetime from string."""
    if value is None:
        return None
    
    if isinstance(value, datetime):
        return value
    
    try:
        # Try ISO format with timezone
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        try:
            # Try without timezone
            return datetime.fromisoformat(value)
        except (ValueError, AttributeError):
            return None


def _parse_decimal(value: Any) -> Optional[Decimal]:
    """Parse Decimal from value."""
    if value is None:
        return None
    
    try:
        return Decimal(str(value))
    except Exception:
        return None
