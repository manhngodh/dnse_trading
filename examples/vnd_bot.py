#!/usr/bin/env python3
"""
Simple VND Trading Bot

This script demonstrates a basic bot structure for trading 'VND' stock.
It connects to DNSE, subscribes to VND market data, and executes
a placeholder strategy on every tick.
"""
import asyncio
import os
import logging
import sys
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VNDBot")

# Load environment variables
try:
    from dotenv import load_dotenv
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv()
except ImportError:
    pass

# Add parent path to sys.path to import dnse_trading if running from examples dir
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dnse_trading.rest.client import DNSEHttpClient
from dnse_trading.websocket.client import DNSEWebSocketClient
from dnse_trading.common.types import DNSEMarketDataTick
from dnse_trading.common.enums import DNSEOrderSide, DNSEOrderType

# Configuration
USERNAME = os.environ.get("DNSE_USERNAME")
PASSWORD = os.environ.get("DNSE_PASSWORD")
ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO")
SYMBOL = "VND"

class VNDTradingBot:
    def __init__(self):
        self.http_client = DNSEHttpClient(
            username=USERNAME,
            password=PASSWORD,
            account_no=ACCOUNT_NO,
        )
        self.ws_client = None
        self.investor_id = None
        self.jwt_token = None
        self.last_price = None

    async def start(self):
        """Start the bot."""
        logger.info("Starting VND Trading Bot...")
        
        try:
            # 1. Connect HTTP Client
            await self.http_client.connect()
            
            # 2. Get Account Info (needed for WebSocket auth)
            account = await self.http_client.get_account_info()
            self.investor_id = account.get("investorId")
            self.jwt_token = self.http_client._auth_provider.jwt_token
            
            logger.info(f"Connected as {account.get('name')} (Investor ID: {self.investor_id})")

            # 3. Start WebSocket Client
            self.ws_client = DNSEWebSocketClient(
                investor_id=self.investor_id,
                jwt_token=self.jwt_token,
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
            self.stop()

    def stop(self):
        """Stop clients."""
        if self.ws_client:
            self.ws_client.disconnect()
        # Note: http_client.disconnect() is async, but we can't await in sync stop.
        # Ideally handle this in async cleanup.
        logger.info("Bot stopped.")

    def on_ws_connected(self):
        """Called when WebSocket connects."""
        logger.info("WebSocket Connected.")
        # Subscribe to VND
        if self.ws_client:
            self.ws_client.subscribe(SYMBOL)

    def on_ws_disconnected(self):
        """Called when WebSocket disconnects."""
        logger.warning("WebSocket Disconnected.")

    def on_tick(self, tick: DNSEMarketDataTick):
        """Handle incoming market data tick."""
        if tick.symbol != SYMBOL:
            return

        # Check if this is a Trade update
        if tick.last_price > 0:
            self.last_price = tick.last_price
            logger.info(f"TRADE: {tick.symbol} Price={tick.last_price} Vol={tick.last_volume}")
        
        # Check if this is a Quote update (Best Bid/Ask)
        if tick.bid_price > 0 or tick.ask_price > 0:
            logger.info(f"QUOTE: {tick.symbol} Bid={tick.bid_price}@{tick.bid_volume} Ask={tick.ask_price}@{tick.ask_volume}")
        
        self.run_strategy(tick)

    def run_strategy(self, tick: DNSEMarketDataTick):
        """
        Execute trading strategy logic.
        
        This is where you would implement your logic, e.g.:
        - Check indicators (RSI, MACD)
        - Compare price levels
        - Place buy/sell orders
        """
        # Example: Simple logic
        # if tick.last_price < Decimal("15.0"):
        #     logger.info("Price is low! Signal: BUY")
        #     # await self.place_buy_order()
        pass

    async def place_buy_order(self):
        """Example async order placement."""
        # Note: This method needs to be called with await from an async context.
        # handling async from sync callback requires ensuring loop exists.
        pass

async def main():
    if not USERNAME or not PASSWORD:
        logger.error("Please set DNSE_USERNAME and DNSE_PASSWORD in .env file")
        return

    bot = VNDTradingBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
