import asyncio
import os
import sys
from decimal import Decimal

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.getcwd()))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from dnse_trading.rest.client import DNSEHttpClient
from dnse_trading.websocket.client import DNSEWebSocketClient
from dnse_trading.common.types import DNSEMarketDataTick

async def get_best_ask():
    username = os.environ.get("DNSE_USERNAME")
    password = os.environ.get("DNSE_PASSWORD")
    account_no = "0001031199"
    symbol = "CHPG2602"

    client = DNSEHttpClient(username=username, password=password, account_no=account_no)
    await client.connect()
    
    account = await client.get_account_info()
    investor_id = account.get("investorId")
    jwt_token = client._auth_provider.jwt_token
    
    price_future = asyncio.Future()

    def on_tick(tick: DNSEMarketDataTick):
        if tick.symbol == symbol and (tick.ask_price > 0 or tick.last_price > 0):
            if not price_future.done():
                price = tick.ask_price if tick.ask_price > 0 else tick.last_price
                price_future.set_result(price)

    ws_client = DNSEWebSocketClient(
        investor_id=investor_id,
        jwt_token=jwt_token,
        on_tick=on_tick,
    )
    
    ws_client.connect()
    ws_client.subscribe(symbol)
    
    try:
        print(f"Fetching best ask for {symbol}...")
        price = await asyncio.wait_for(price_future, timeout=10.0)
        print(f"Best Ask: {price}")
    except asyncio.TimeoutError:
        print("Timeout waiting for price.")
    finally:
        ws_client.disconnect()
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(get_best_ask())
