"""
Type definitions for DNSE API responses and data structures.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DNSEAccountInfo:
    """DNSE account information."""
    investor_id: str
    name: str
    custody_code: str
    mobile: str
    email: str


@dataclass
class DNSESubAccount:
    """DNSE sub-account (trading account)."""
    account_no: str
    account_type: str
    is_primary: bool


@dataclass
class DNSELoanPackage:
    """DNSE loan package for margin trading."""
    loan_package_id: int
    name: str
    initial_rate: Decimal
    maintenance_rate: Decimal
    is_active: bool


@dataclass
class DNSEBuyingPower:
    """DNSE buying/selling power."""
    account_no: str
    symbol: str
    max_buy_qty: int
    max_sell_qty: int
    available_cash: Decimal
    

@dataclass
class DNSEOrderResponse:
    """DNSE order response from API."""
    id: int
    side: str
    account_no: str
    investor_id: str
    symbol: str
    price: Decimal
    quantity: int
    order_type: str
    order_status: str
    fill_quantity: int
    last_quantity: int
    last_price: Optional[Decimal]
    average_price: Optional[Decimal]
    trans_date: str
    created_date: datetime
    modified_date: Optional[datetime]
    tax_rate: Optional[Decimal]
    fee_rate: Optional[Decimal]
    leave_quantity: int
    canceled_quantity: int
    price_secure: Optional[Decimal]
    custody: str
    channel: str
    loan_package_id: Optional[int]
    initial_rate: Optional[Decimal]
    error: Optional[str]


@dataclass
class DNSEHolding:
    """DNSE stock holding/position."""
    symbol: str
    quantity: int
    available_quantity: int
    average_price: Decimal
    market_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal


@dataclass
class DNSEDerivativePosition:
    """DNSE derivative position."""
    symbol: str
    side: str  # Long/Short
    quantity: int
    average_price: Decimal
    market_price: Decimal
    unrealized_pnl: Decimal
    initial_margin: Decimal
    maintenance_margin: Decimal


@dataclass
class DNSEMarketDataTick:
    """DNSE market data tick from WebSocket."""
    symbol: str
    timestamp: datetime
    last_price: Decimal
    last_volume: int
    bid_price: Decimal
    bid_volume: int
    ask_price: Decimal
    ask_volume: int
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Optional[Decimal]
    total_volume: int
    total_value: Decimal


@dataclass 
class DNSETokens:
    """DNSE authentication tokens."""
    jwt_token: str
    jwt_expires_at: datetime
    trading_token: Optional[str] = None
    trading_token_expires_at: Optional[datetime] = None
    
    @property
    def is_jwt_expired(self) -> bool:
        """Check if JWT token is expired."""
        return datetime.now() >= self.jwt_expires_at
    
    @property
    def is_trading_token_expired(self) -> bool:
        """Check if trading token is expired."""
        if self.trading_token is None or self.trading_token_expires_at is None:
            return True
        return datetime.now() >= self.trading_token_expires_at
