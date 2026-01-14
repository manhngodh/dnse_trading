"""
Market data parsing utilities.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from ..common.types import DNSEMarketDataTick


def parse_market_data_tick(symbol: str, data: dict) -> Optional[DNSEMarketDataTick]:
    """
    Parse market data tick from WebSocket message.
    
    Parameters
    ----------
    symbol : str
        The symbol for this tick.
    data : dict
        Raw message data from WebSocket.
    
    Returns
    -------
    DNSEMarketDataTick | None
        Parsed tick or None if parsing fails.
    """
    try:
        # Parse timestamp
        timestamp = _parse_timestamp(data)
        
        return DNSEMarketDataTick(
            symbol=symbol,
            timestamp=timestamp,
            last_price=_safe_decimal(data.get("lastPrice") or data.get("last_price") or data.get("matchedPrice")),
            last_volume=_safe_int(data.get("lastVolume") or data.get("last_volume") or data.get("matchedVolume")),
            bid_price=_safe_decimal(data.get("bidPrice") or data.get("bid_price") or data.get("bestBid")),
            bid_volume=_safe_int(data.get("bidVolume") or data.get("bid_volume") or data.get("bestBidVolume")),
            ask_price=_safe_decimal(data.get("askPrice") or data.get("ask_price") or data.get("bestAsk")),
            ask_volume=_safe_int(data.get("askVolume") or data.get("ask_volume") or data.get("bestAskVolume")),
            open_price=_safe_decimal(data.get("openPrice") or data.get("open_price") or data.get("open")),
            high_price=_safe_decimal(data.get("highPrice") or data.get("high_price") or data.get("high")),
            low_price=_safe_decimal(data.get("lowPrice") or data.get("low_price") or data.get("low")),
            close_price=_safe_decimal(data.get("closePrice") or data.get("close_price") or data.get("close")),
            total_volume=_safe_int(data.get("totalVolume") or data.get("total_volume") or data.get("accumulatedVolume")),
            total_value=_safe_decimal(data.get("totalValue") or data.get("total_value") or data.get("accumulatedValue")),
        )
    except Exception:
        return None


def _parse_timestamp(data: dict) -> datetime:
    """Parse timestamp from various possible fields."""
    timestamp_fields = ["time", "timestamp", "tradingTime", "matchedTime"]
    
    for field in timestamp_fields:
        value = data.get(field)
        if value:
            try:
                if isinstance(value, (int, float)):
                    # Unix timestamp (seconds or milliseconds)
                    if value > 1e12:
                        return datetime.fromtimestamp(value / 1000)
                    return datetime.fromtimestamp(value)
                elif isinstance(value, str):
                    # ISO format
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                continue
    
    return datetime.now()


def _safe_decimal(value: Any) -> Decimal:
    """Safely convert value to Decimal."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _safe_int(value: Any) -> int:
    """Safely convert value to int."""
    if value is None:
        return 0
    try:
        return int(value)
    except Exception:
        return 0


def parse_order_book_level(data: dict) -> dict:
    """
    Parse order book level from market data.
    
    Parameters
    ----------
    data : dict
        Raw order book level data.
    
    Returns
    -------
    dict
        Parsed level with price and volume.
    """
    return {
        "price": _safe_decimal(data.get("price")),
        "volume": _safe_int(data.get("volume") or data.get("qty")),
        "order_count": _safe_int(data.get("orderCount") or data.get("numOrders")),
    }


def parse_trade(data: dict) -> dict:
    """
    Parse trade from market data.
    
    Parameters
    ----------
    data : dict
        Raw trade data.
    
    Returns
    -------
    dict
        Parsed trade with price, volume, and time.
    """
    return {
        "price": _safe_decimal(data.get("price") or data.get("matchedPrice")),
        "volume": _safe_int(data.get("volume") or data.get("matchedVolume")),
        "time": _parse_timestamp(data),
        "side": data.get("side") or data.get("buySellType"),
    }
