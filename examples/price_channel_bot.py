#!/usr/bin/env python3
"""
Price Channel Grid Bot

This script implements a "Price Channel Grid" strategy:
1.  Calculates a Price Channel (High/Low) over a specified rolling window (default 4-5 hours).
2.  Maintains a Grid setup:
    -   Buy Limit at Channel Low.
    -   Sell Limit at Channel High.

Note: Since historical data is not available via the current API, this bot uses a
"Rolling Window" approach. It accumulates real-time ticks to build the channel.
"""
import asyncio
import os
import logging
import sys
import time
from collections import deque
from decimal import Decimal
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PriceChannelBot")

# Load environment variables
try:
    from dotenv import load_dotenv
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv()
except ImportError:
    pass

# Add parent path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dnse_trading.rest.client import DNSEHttpClient
from dnse_trading.websocket.client import DNSEWebSocketClient
from dnse_trading.common.types import DNSEMarketDataTick
from dnse_trading.common.enums import DNSEOrderSide, DNSEOrderType

# Configuration
USERNAME = os.environ.get("DNSE_USERNAME")
PASSWORD = os.environ.get("DNSE_PASSWORD")
ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO")

# Strategy Settings
SYMBOL = "VND"          # Target Symbol
WINDOW_HOURS = 4        # Channel Duration in Hours
QUANTITY = 100          # Order Quantity
PRICE_PADDING = Decimal("0") # Optional: Place order slightly inside/outside channel (e.g., 50 for 50 VND)

class RollingPriceChannel:
    """Maintains a rolling window of prices to calculate High/Low."""
    def __init__(self, window_seconds: float):
        self.window_seconds = window_seconds
        self.prices: deque = deque() # Stores (timestamp, price)
        self.high: Optional[Decimal] = None
        self.low: Optional[Decimal] = None

    def add_price(self, price: Decimal, timestamp: float):
        """Add a new price observation."""
        self.prices.append((timestamp, price))
        self._prune(timestamp)
        self._recalculate()

    def _prune(self, current_time: float):
        """Remove old prices outside the window."""
        cutoff = current_time - self.window_seconds
        while self.prices and self.prices[0][0] < cutoff:
            self.prices.popleft()

    def _recalculate(self):
        """Recalculate High/Low from current window."""
        if not self.prices:
            self.high = None
            self.low = None
            return

        # Optimization: We could be smarter than O(N) here, but for simple bot usually fine
        # unless tick density is massive.
        prices = [p for _, p in self.prices]
        self.high = max(prices)
        self.low = min(prices)

    def is_ready(self) -> bool:
        """
        Check if we have enough data to form a 'valid' channel.
        For this implementation, we consider it valid as soon as we have data,
        but user should know it expands over time.
        """
        return bool(self.prices)

    @property
    def channel(self) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        return self.high, self.low

class PriceChannelBot:
    def __init__(self):
        self.http_client = DNSEHttpClient(
            username=USERNAME,
            password=PASSWORD,
            account_no=ACCOUNT_NO,
            otp_callback=self.get_otp_input
        )
        self.ws_client = None
        self.channel = RollingPriceChannel(window_seconds=WINDOW_HOURS * 3600)
        
        # State
        self.active_buy_order_id = None
        self.active_sell_order_id = None
        self.investor_id = None
        
        # Rate limiting logic for order updates
        self.last_order_update = 0
        self.update_interval = 30 # Seconds between checking/moving orders

    def get_otp_input(self):
        return input("Enter OTP for Trading: ").strip()

    async def start(self):
        logger.info(f"Starting Price Channel Bot for {SYMBOL} ({WINDOW_HOURS}h window)")
        
        await self.http_client.connect()
        
        # Authenticate details
        account = await self.http_client.get_account_info()
        self.investor_id = account.get("investorId")
        logger.info(f"Connected: {account.get('name')} ({self.investor_id})")

        # Start Websocket
        self.ws_client = DNSEWebSocketClient(
            investor_id=self.investor_id,
            jwt_token=self.http_client._auth_provider.jwt_token,
            on_tick=self.on_tick,
            on_connected=self.on_ws_connected
        )
        self.ws_client.connect()

        # Main Loop
        try:
            while True:
                await asyncio.sleep(1)
                await self.check_orders()
        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            self.stop()

    def stop(self):
        if self.ws_client:
            self.ws_client.disconnect()
        # self.http_client.disconnect() # async, can't await here easily

    def on_ws_connected(self):
        logger.info("WS Connected")
        self.ws_client.subscribe(SYMBOL)

    def on_tick(self, tick: DNSEMarketDataTick):
        if tick.symbol != SYMBOL:
            return
        
        price = None
        if tick.last_price and tick.last_price > 0:
            price = tick.last_price
        elif tick.bid_price and tick.ask_price and tick.bid_price > 0 and tick.ask_price > 0:
            price = (tick.bid_price + tick.ask_price) / 2
        elif tick.bid_price and tick.bid_price > 0:
            price = tick.bid_price
        elif tick.ask_price and tick.ask_price > 0:
            price = tick.ask_price
            
        if price:
            self.channel.add_price(price, time.time())
            
            # high, low = self.channel.channel
            # logger.debug(f"Price: {price}. Channel: [{low}, {high}]")

    async def check_orders(self):
        """Periodically check and update orders based on channel."""
        now = time.time()
        if now - self.last_order_update < self.update_interval:
            return
        
        high, low = self.channel.channel
        if not high or not low or high == low:
            # Not enough data or flat line
            return

        target_buy_price = low
        target_sell_price = high
        
        logger.info(f"Channel Update: [{low} - {high}]. Current Orders: Buy@{self.active_buy_order_id}, Sell@{self.active_sell_order_id}")

        # Note: In a real robust system, we would:
        # 1. Fetch open orders map from API to reconcile state (in case filled/cancelled externally).
        # 2. Only move order if difference > threshold to avoid spamming updates.
        
        # For this example, we'll implement a simple "Place if none" logic.
        # Moving existing orders requires Cancel + Place.
        
        if not self.active_buy_order_id:
            await self.place_limit_order(DNSEOrderSide.BUY, target_buy_price)
        
        if not self.active_sell_order_id:
            await self.place_limit_order(DNSEOrderSide.SELL, target_sell_price)
        
        self.last_order_update = now

    async def place_limit_order(self, side: DNSEOrderSide, price: Decimal):
        """Place a limit order."""
        # DRY RUN SAFETY (Uncomment to enable real trading)
        if side == DNSEOrderSide.BUY:
             logger.info(f"[SIMULATION] Placing BUY Limit @ {price}")
             self.active_buy_order_id = "SIM_BUY_ID"
             return 
        elif side == DNSEOrderSide.SELL:
             logger.info(f"[SIMULATION] Placing SELL Limit @ {price}")
             self.active_sell_order_id = "SIM_SELL_ID"
             return

        # REAL TRADING CODE (Commented out for safety as per standard practice unless requested)
        # try:
        #     res = await self.http_client.place_order(
        #         symbol=SYMBOL,
        #         side=side,
        #         order_type=DNSEOrderType.LIMIT,
        #         price=price,
        #         quantity=QUANTITY
        #     )
        #     order_id = res['id']
        #     logger.info(f"Placed {side.name} Order {order_id} @ {price}")
        #     if side == DNSEOrderSide.BUY:
        #         self.active_buy_order_id = order_id
        #     else:
        #         self.active_sell_order_id = order_id
        # except Exception as e:
        #     logger.error(f"Failed to place order: {e}")

async def main():
    if not USERNAME:
        logger.error("Env vars not set properly.")
        return
    
    bot = PriceChannelBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
