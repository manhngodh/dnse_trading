"""
DNSE-specific enums for order types, sides, and statuses.
"""
from enum import Enum


class DNSEOrderSide(str, Enum):
    """DNSE order side values."""
    BUY = "NB"    # Mua (Buy)
    SELL = "NS"   # Bán (Sell)


class DNSEOrderType(str, Enum):
    """DNSE order type values."""
    LIMIT = "LO"           # Limit order
    MARKET = "MP"          # Market price
    MARKET_TO_LIMIT = "MTL"  # Market-to-limit
    AT_OPEN = "ATO"        # At-the-open
    AT_CLOSE = "ATC"       # At-the-close
    MATCH_OR_KILL = "MOK"  # Match or kill
    MATCH_AND_KILL = "MAK" # Match and kill
    POST_CLOSE = "PLO"     # Post-close limit order


class DNSEOrderStatus(str, Enum):
    """DNSE order status values."""
    PENDING = "pending"               # Pending to send
    PENDING_NEW = "pendingNew"        # Pending new
    NEW = "new"                       # Waiting to match
    PARTIALLY_FILLED = "partiallyFilled"  # Partially matched
    FILLED = "filled"                 # Fully matched
    REJECTED = "rejected"             # Rejected
    EXPIRED = "expired"               # Expired in session
    DONE_FOR_DAY = "doneForDay"       # Done for day
    CANCELED = "canceled"             # Canceled


class DNSEMarketType(str, Enum):
    """DNSE market type for different trading products."""
    BASE = "base"           # Base securities (stocks)
    DERIVATIVE = "derivative"  # Derivatives (futures, options)


class DNSEAccountType(str, Enum):
    """DNSE account types."""
    NORMAL = "normal"       # Normal account
    MARGIN = "margin"       # Margin account


class DNSEExchange(str, Enum):
    """Vietnamese stock exchanges."""
    HOSE = "HOSE"   # Ho Chi Minh Stock Exchange
    HNX = "HNX"     # Hanoi Stock Exchange
    UPCOM = "UPCOM" # Unlisted Public Company Market
