#!/usr/bin/env python3
"""
Portfolio Take Profit & Cost Reduction Bot

This strategy monitors an existing position and:
1.  **Take Profit**: Sells a portion if Profit > target (e.g., 1%).
2.  **Accumulate**: Buys a portion if Price < target (e.g., -1%) - Buying the dip.
3.  **Cost Reduction (Crisis Mode)**: If PnL < -10% (Deep Loss):
    -   Scalps volatility: Sells on small rallies, buys back on dips.
    -   Ensures net position size does not strictly increase beyond initial snapshot.

Usage:
    python examples/portfolio_take_profit.py
"""
import asyncio
import os
import logging
import sys
import time
from decimal import Decimal
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PortfolioBot")

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
SYMBOL = "VND"
SIMULATION_MODE = True  # Set to False to trade real money

# Constants
TAKE_PROFIT_THRESHOLD = Decimal("0.01")  # +1%
ACCUMULATE_THRESHOLD = Decimal("-0.01")  # -1%
CRISIS_THRESHOLD = Decimal("-0.10")      # -10% PnL triggers Crisis Mode

ORDER_SIZE_PCT = 0.10     # 10% of position for TP/Accumulate
SCALP_SIZE_PCT = 0.05     # 5% for Cost Reduction Scalps
SCALP_STEP = Decimal("0.01") # 1% step for scalping

COOLDOWN_SECONDS = 60     # Seconds between orders to avoid spam

class PortfolioTakeProfitBot:
    def __init__(self):
        self.http_client = DNSEHttpClient(
            username=USERNAME,
            password=PASSWORD,
            account_no=ACCOUNT_NO,
            otp_callback=self.get_otp_input
        )
        self.ws_client = None
        
        # Portfolio State
        self.avg_cost: Decimal = Decimal("0")
        self.quantity: int = 0
        self.initial_quantity: int = 0 # Snapshot for Crisis Mode constraint
        
        # Market State
        self.last_bid: Decimal = Decimal("0")
        self.last_ask: Decimal = Decimal("0")
        self.last_trade_price: Decimal = Decimal("0") # Reference for scalping
        
        # Bot State
        self.investor_id = None
        self.last_order_time = 0
        self.in_crisis_mode = False

    def get_otp_input(self):
        return input("Enter OTP for Trading: ").strip()

    async def start(self):
        logger.info(f"Starting Portfolio Bot for {SYMBOL}")
        logger.info(f"Mode: {'SIMULATION' if SIMULATION_MODE else 'REAL TRADING'}")
        
        await self.http_client.connect()
        
        # Authenticate
        account = await self.http_client.get_account_info()
        self.investor_id = account.get("investorId")
        logger.info(f"Connected: {account.get('name')} ({self.investor_id})")

        # Initial Portfolio Fetch
        await self.update_holdings()
        if self.quantity == 0:
            logger.warning(f"No holdings found for {SYMBOL}. Bot will watch for entry or manual update.")
        else:
            self.initial_quantity = self.quantity
            logger.info(f"Initial Position: {self.quantity} @ {self.avg_cost}")

        # Start WebSocket
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
                await asyncio.sleep(60) # Periodic holding refresh
                await self.update_holdings()
        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            self.stop()

    def stop(self):
        if self.ws_client:
            self.ws_client.disconnect()
        # self.http_client.disconnect()

    def on_ws_connected(self):
        logger.info("WS Connected")
        self.ws_client.subscribe(SYMBOL)

    async def update_holdings(self):
        """Fetch current holdings from API."""
        try:
            holdings = await self.http_client.get_holdings()
            found = False
            for h in holdings:
                if h.get("symbol") == SYMBOL:
                    raw_qty = h.get("totalQuantity") or h.get("quantity")
                    raw_cost = h.get("avgPrice") or h.get("averagePrice")
                    
                    new_qty = int(raw_qty) if raw_qty else 0
                    new_cost = Decimal(str(raw_cost)) if raw_cost else Decimal("0")
                    
                    if new_qty != self.quantity:
                        logger.info(f"Holdings Updated: {self.quantity} -> {new_qty} (Cost: {new_cost})")
                    
                    self.quantity = new_qty
                    self.avg_cost = new_cost
                    found = True
                    break
            
            if not found and self.quantity > 0:
                logger.warning("Position closed or not found.")
                self.quantity = 0
                self.avg_cost = 0
                
        except Exception as e:
            logger.error(f"Failed to update holdings: {e}")

        # [SIMULATION] Inject Mock Data if empty (Uncomment for testing without holdings)
        # if SIMULATION_MODE and self.quantity == 0 and self.avg_cost == 0:
        #     self.quantity = 1000
        #     # Let's set it near market price if possible, or just a fixed value. 
        #     # If current market is ~20.5 (from previous run), let's set it to 20.0 to test Profit > 1%
        #     self.avg_cost = Decimal("20.0")
        #     logger.info(f"[SIMULATION] Injected Mock Holdings: {self.quantity} @ {self.avg_cost}")
        #     if self.initial_quantity == 0:
        #         self.initial_quantity = self.quantity

    def on_tick(self, tick: DNSEMarketDataTick):
        if tick.symbol != SYMBOL:
            return
        
        # Update Market Data
        # We prefer Bid/Ask for precise triggers, fallback to Last
        if tick.bid_price and tick.bid_price > 0:
            self.last_bid = tick.bid_price
        if tick.ask_price and tick.ask_price > 0:
            self.last_ask = tick.ask_price
        
        # If we have no Bid/Ask yet, maybe use last_price as proxy
        if self.last_bid == 0 and tick.last_price and tick.last_price > 0:
            self.last_bid = tick.last_price
        if self.last_ask == 0 and tick.last_price and tick.last_price > 0:
            self.last_ask = tick.last_price

        if self.quantity == 0 or self.avg_cost == 0:
            return
        
        if self.last_bid == 0 or self.last_ask == 0:
            return

        # Calculate PnL % based on avg cost
        # For Selling (Profit or Scalp Sell), we sell into the BID
        pnl_bid = (self.last_bid - self.avg_cost) / self.avg_cost
        
        # For Buying (Accumulate or Scalp Buy), we buy from the ASK
        pnl_ask = (self.last_ask - self.avg_cost) / self.avg_cost

        # Determine Mode
        if pnl_bid < CRISIS_THRESHOLD:
            if not self.in_crisis_mode:
                logger.warning(f"ENTERING CRISIS MODE (PnL {pnl_bid*100:.2f}% < {CRISIS_THRESHOLD*100}%)")
                self.in_crisis_mode = True
                self.last_trade_price = self.last_bid # Reset reference
        else:
            if self.in_crisis_mode and pnl_bid > CRISIS_THRESHOLD * Decimal("0.8"): # Hysteresis exit
                 logger.info("EXITING CRISIS MODE")
                 self.in_crisis_mode = False

        self._evaluate_strategy(pnl_bid, pnl_ask)

    def _evaluate_strategy(self, pnl_bid: Decimal, pnl_ask: Decimal):
        now = time.time()
        if now - self.last_order_time < COOLDOWN_SECONDS:
            return

        if self.in_crisis_mode:
            self._handle_crisis_mode()
        else:
            self._handle_normal_mode(pnl_bid, pnl_ask)

    def _handle_normal_mode(self, pnl_bid: Decimal, pnl_ask: Decimal):
        # Take Profit
        if pnl_bid >= TAKE_PROFIT_THRESHOLD:
            qty_to_sell = max(10, int(self.quantity * ORDER_SIZE_PCT))
            logger.info(f"Signal: TAKE PROFIT (+{pnl_bid*100:.2f}%). Selling {qty_to_sell}.")
            asyncio.create_task(self.place_order(DNSEOrderSide.SELL, self.last_bid, qty_to_sell))
            return

        # Accumulate (Buy Dip)
        if pnl_ask <= ACCUMULATE_THRESHOLD:
            qty_to_buy = max(10, int(self.quantity * ORDER_SIZE_PCT))
            logger.info(f"Signal: ACCUMULATE ({pnl_ask*100:.2f}%). Buying {qty_to_buy}.")
            asyncio.create_task(self.place_order(DNSEOrderSide.BUY, self.last_ask, qty_to_buy))
            return

    def _handle_crisis_mode(self):
        # Scalping Logic:
        # Sell if price rallied X% above last ref
        # Buy if price dropped X% below last ref
        
        if self.last_trade_price == 0:
            self.last_trade_price = self.last_bid
            return

        price_change = (self.last_bid - self.last_trade_price) / self.last_trade_price

        # Sell Rally (Scalp Sell)
        if price_change >= SCALP_STEP:
            if self.quantity <= self.initial_quantity: # Only if we haven't already sold too much? 
                # Actually, in crisis we want to reduce cost. 
                # Constraint: We don't want to INCREASE size net-net. 
                # So selling is always allowed (reduces size).
                qty_to_sell = max(10, int(self.quantity * SCALP_SIZE_PCT))
                logger.info(f"Signal: CRISIS SCALP SELL (Rally +{price_change*100:.2f}%). Selling {qty_to_sell}.")
                asyncio.create_task(self.place_order(DNSEOrderSide.SELL, self.last_bid, qty_to_sell))
                self.last_trade_price = self.last_bid # Update ref
                return

        # Buy Back Dip (Scalp Buy)
        # We calculate change based on Ask for buying
        price_change_ask = (self.last_ask - self.last_trade_price) / self.last_trade_price
        
        if price_change_ask <= -SCALP_STEP:
            # Constraint: Current Qty < Initial Qty to allow buy back
            # We shouldn't hold MORE than we started with.
            if self.quantity < self.initial_quantity:
                qty_to_buy = max(10, int(self.quantity * SCALP_SIZE_PCT))
                logger.info(f"Signal: CRISIS SCALP BUY (Dip {price_change_ask*100:.2f}%). Buying {qty_to_buy}.")
                asyncio.create_task(self.place_order(DNSEOrderSide.BUY, self.last_ask, qty_to_buy))
                self.last_trade_price = self.last_ask # Update ref
                return

    async def place_order(self, side: DNSEOrderSide, price: Decimal, quantity: int):
        self.last_order_time = time.time()
        
        if SIMULATION_MODE:
            logger.info(f"[SIMULATION] Placing {side.name} Order: {quantity} @ {price}")
            # Mock update for simulation
            if side == DNSEOrderSide.BUY:
                # Weighted Avg Cost update approximation
                total_val = (self.quantity * self.avg_cost) + (quantity * price)
                self.quantity += quantity
                self.avg_cost = total_val / self.quantity
            else:
                self.quantity -= quantity
                # Cost basis doesn't change on sell, but realized PnL happens
            
            logger.info(f"[SIMULATED POST-TRADE] Qty: {self.quantity}, AvgCost: {self.avg_cost:.2f}")
            return

        # Real Execution
        try:
            res = await self.http_client.place_order(
                symbol=SYMBOL,
                side=side,
                order_type=DNSEOrderType.LIMIT,
                price=price,
                quantity=quantity
            )
            logger.info(f"Order Placed: {res.get('id')}")
        except Exception as e:
            logger.error(f"Order Placement Failed: {e}")

async def main():
    if not USERNAME:
        logger.error("Env vars not set properly.")
        return
    
    bot = PortfolioTakeProfitBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
