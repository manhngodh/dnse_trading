# DNSE Trading

DNSE Lightspeed API Trading Adapter for Vietnamese Securities (KRX System).

## Features

- **REST API Client**: Full async HTTP client for trading operations
- **WebSocket Client**: Real-time market data via MQTT over WebSocket
- **2-Layer Authentication**: JWT token + OTP trading token support
- **Order Management**: Place, cancel, and query orders for stocks and derivatives
- **Position Tracking**: Account info, holdings, and derivative positions

## API Endpoints Supported

### Trading
- Login & OTP authentication
- Account info & sub-accounts
- Buying power queries
- Order placement (stocks & derivatives)
- Order cancellation
- Order book queries

### Market Data
- Real-time price feeds via WebSocket (MQTT)
- Quote and trade tick streaming

## Installation

```bash
pip install aiohttp paho-mqtt
```

## Quick Start

```python
import asyncio
from dnse_trading.http.client import DNSEHttpClient
from dnse_trading.common.enums import DNSEOrderSide, DNSEOrderType
from decimal import Decimal

async def main():
    # Create client
    client = DNSEHttpClient(
        username="your_username",
        password="your_password",
        account_no="your_account_no",
    )
    
    # Connect and authenticate
    await client.connect()
    
    # Get account info
    account = await client.get_account_info()
    print(f"Logged in as: {account['name']}")
    
    # Request trading token (requires OTP)
    await client.request_trading_token(otp="123456")
    
    # Place an order
    response = await client.place_order(
        symbol="VNM",
        side=DNSEOrderSide.BUY,
        order_type=DNSEOrderType.LIMIT,
        price=Decimal("75000"),
        quantity=100,
    )
    print(f"Order ID: {response['id']}")
    
    await client.disconnect()

asyncio.run(main())
```

## Project Structure

```
dnse_trading/
├── __init__.py           # Package exports
├── config.py             # Configuration classes
├── factories.py          # Client factories
├── common/
│   ├── enums.py          # Order types, sides, statuses
│   ├── constants.py      # API endpoints, URLs
│   └── types.py          # Data type definitions
├── http/
│   ├── client.py         # Async HTTP client
│   ├── auth.py           # Authentication provider
│   └── endpoints.py      # URL builders
├── websocket/
│   └── client.py         # MQTT WebSocket client
├── data/
│   └── client.py         # Data client (NautilusTrader)
├── execution/
│   └── client.py         # Execution client (NautilusTrader)
└── parsing/
    └── orders.py         # Response parsers
```

## License

MIT
