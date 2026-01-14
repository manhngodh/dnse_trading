#!/usr/bin/env python3
"""
Intraday Scalping Bot (Bollinger Bands)
---------------------------------------
A standalone trading bot for DNSE Trading that implements a mean reversion strategy.
It uses Bollinger Bands to identify "Buy Low" (Lower Band) and "Sell High" (Upper Band) opportunities.

Market: T+2.5 (Vietnam)
Mode: Paper Trading (Simulation) by default to prevent accidental locked inventory.
"""

import asyncio
import os
import logging
import sys
import statistics
from collections import deque
from decimal import Decimal
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("IntradayScalp")

# Load environment variables
try:
    from dotenv import load_dotenv
    # Look for .env in current or parent directories
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv()
except ImportError:
    pass

# Add parent path to sys.path to import dnse_trading if running from examples dir
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dnse_trading.rest.client import DNSEHttpClient
from dnse_trading.websocket.client import DNSEWebSocketClient
from dnse_trading.common.types import DNSEMarketDataTick

# Configuration
USERNAME = os.environ.get("DNSE_USERNAME")
PASSWORD = os.environ.get("DNSE_PASSWORD")
ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO")
SYMBOL = "VND"  # Default symbol, can be changed

# Strategy Parameters
WINDOW_SIZE = 20        # Moving average window (e.g., 20 ticks or candles)
STD_DEV_MULTIPLIER = 2.0 # Bollinger Band width
PAPER_TRADING = True    # Set to False to enable REAL TRADING (Risk!)

class IntradayScalpBot:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.http_client = DNSEHttpClient(
            username=USERNAME,
            password=PASSWORD,
            account_no=ACCOUNT_NO,
        )
        self.ws_client = None
        self.price_history = deque(maxlen=WINDOW_SIZE)
        
        # State
        self.position = 0
        self.avg_price = Decimal("0")
        
        logger.info(f"Initialized Scalp Bot for {symbol} (Window={WINDOW_SIZE})")

    async def start(self):
        """Start the bot."""
        logger.info("Starting Intraday Scalp Bot...")
        
        if not USERNAME or not PASSWORD:
            logger.error("Missing credentials! Please set DNSE_USERNAME and DNSE_PASSWORD in .env")
            return

        try:
            # 1. Connect HTTP Client
            await self.http_client.connect()
            
            # 2. Get Account Info (needed for WebSocket auth)
            account = await self.http_client.get_account_info()
            investor_id = account.get("investorId")
            jwt_token = self.http_client._auth_provider.jwt_token
            
            logger.info(f"Connected as {account.get('name')} (Investor ID: {investor_id})")

            # 3. Start WebSocket Client
            self.ws_client = DNSEWebSocketClient(
                investor_id=investor_id,
                jwt_token=jwt_token,
                on_tick=self.on_tick,
                on_connected=self.on_ws_connected,
                on_disconnected=self.on_ws_disconnected
            )
            
            self.ws_client.connect()
            
            # 4. Keep running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.stop()

    async def stop(self):
        """Stop clients."""
        if self.ws_client:
            self.ws_client.disconnect()
        # Ensure HTTP client is closed if it has an active session
        if self.http_client._session and not self.http_client._session.closed:
             await self.http_client._session.close()
        logger.info("Bot stopped.")

    def on_ws_connected(self):
        """Called when WebSocket connects."""
        logger.info("WebSocket Connected.")
        if self.ws_client:
            self.ws_client.subscribe(self.symbol)

    def on_ws_disconnected(self):
        """Called when WebSocket disconnects."""
        logger.warning("WebSocket Disconnected.")

    def on_tick(self, tick: DNSEMarketDataTick):
        """Handle incoming market data tick."""
        if tick.symbol != self.symbol:
            return

        # Only process if we have a valid last price
        if tick.last_price <= 0:
            return

        current_price = tick.last_price
        
        # Add to history
        self.price_history.append(float(current_price))
        
        # Need enough data to calculate bands
        if len(self.price_history) < WINDOW_SIZE:
            logger.debug(f"Gathering data... {len(self.price_history)}/{WINDOW_SIZE}")
            return

        # Calculate Bollinger Bands
        sma = statistics.mean(self.price_history)
        stdev = statistics.stdev(self.price_history)
        upper_band = Decimal(str(sma + (stdev * STD_DEV_MULTIPLIER)))
        lower_band = Decimal(str(sma - (stdev * STD_DEV_MULTIPLIER)))
        
        # Log status periodically or on significant change
        # logger.info(f"Price: {current_price} | Upper: {upper_band:.2f} | Lower: {lower_band:.2f}")

        # Check Signals
        self.check_signals(current_price, upper_band, lower_band)

    def check_signals(self, price: Decimal, upper: Decimal, lower: Decimal):
        """
        Check for Buy/Sell signals based on Bollinger Bands.
        Signal: T+0 / Intraday Scalping
        """
        
        # BUY SIGNAL: Price touches or drops below Lower Band
        # Condition: strict "less than" or "cross below" logic.
        # Here we use simple "is below" for immediate reaction.
        if price <= lower:
            self.execute_signal("BUY", price, "Price below Lower Bollinger Band")

        # SELL SIGNAL: Price touches or exceeds Upper Band
        elif price >= upper:
            self.execute_signal("SELL", price, "Price above Upper Bollinger Band")

    def execute_signal(self, side: str, price: Decimal, reason: str):
        """Execute or log the signal."""
        
        if side == "BUY":
            # Simple logic: Buy if we don't have a position (or add more if pyramiding, but let's keep it simple: 1 active trade)
            if self.position == 0:
                logger.info(f"🚀 SIGNAL: BUY {self.symbol} @ {price} | Reason: {reason}")
                
                if PAPER_TRADING:
                    self.position = 100 # Simulated quantity
                    self.avg_price = price
                    logger.info(f"PAPER TRADE: Bought 100 {self.symbol} at {price}")
                else:
                    # REAL TRADING LOGIC WOULD GO HERE
                    # await self.http_client.place_order(...)
                    pass

        elif side == "SELL":
            # Sell if we have a position
            if self.position > 0:
                # Calculate PnL
                pnl = (price - self.avg_price) * self.position
                pnl_percent = ((price - self.avg_price) / self.avg_price) * 100
                
                logger.info(f"📉 SIGNAL: SELL {self.symbol} @ {price} | Reason: {reason}")
                logger.info(f"PAPER TRADE: Sold {self.position} {self.symbol} at {price}. PnL: {pnl} ({pnl_percent:.2f}%)")
                
                if PAPER_TRADING:
                    self.position = 0
                    self.avg_price = Decimal("0")
                else:
                    # REAL TRADING LOGIC
                    pass

async def main():
    bot = IntradayScalpBot(SYMBOL)
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
