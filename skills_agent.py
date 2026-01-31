#!/usr/bin/env python3
import asyncio
import os
import sys
import argparse
import logging
from decimal import Decimal
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from dnse_trading.rest.client import DNSEHttpClient
from dnse_trading.websocket.client import DNSEWebSocketClient
from dnse_trading.common.types import DNSEMarketDataTick

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("SkillsAgent")

# Constants
ACCOUNTS = {
    "spacex": "0001010274",
    "rocket": "0001031199"
}
LOAN_PACKAGE_ID = 1775 # "GD Tiền mặt"
CONDITIONAL_ORDER_URL = "https://api.dnse.com.vn/conditional-order-api/v1/orders"
DEAL_SERVICE_URL = "https://api.dnse.com.vn/deal-service/deals"

class SkillsAgent:
    def __init__(self, args):
        self.args = args
        self.username = os.environ.get("DNSE_USERNAME")
        self.password = os.environ.get("DNSE_PASSWORD")
        self.otp_val = args.otp
        self.clients = {} # Cache clients per account

    def get_otp(self):
        if self.otp_val:
            return self.otp_val
        print("Please enter your Smart OTP:")
        self.otp_val = input().strip()
        return self.otp_val

    async def get_client(self, account_alias="rocket"):
        """Get or create an authenticated client for a specific account."""
        account_no = ACCOUNTS.get(account_alias, account_alias)
        
        if account_no in self.clients:
            return self.clients[account_no]
            
        client = DNSEHttpClient(
            username=self.username,
            password=self.password,
            account_no=account_no,
            otp_callback=self.get_otp
        )
        await client.connect()
        self.clients[account_no] = client
        return client

    async def cleanup(self):
        for client in self.clients.values():
            await client.disconnect()

    # --- SKILL 1: MONITOR ---
    async def skill_monitor(self):
        symbol = self.args.symbol.upper()
        target = float(self.args.price) if self.args.price else None
        
        logger.info(f"👀  [MONITOR] Watching {symbol}..." + (f" (Target: {target})" if target else ""))
        
        # Use primary client for websocket auth
        client = await self.get_client("rocket") 
        account_info = await client.get_account_info()
        investor_id = account_info.get("investorId")
        jwt = client._auth_provider.jwt_token
        
        stop_event = asyncio.Event()

        def on_tick(tick: DNSEMarketDataTick):
            if tick.symbol != symbol: return
            
            # Prefer matching price, then bid/ask/last
            price = tick.last_price
            if price == 0 and tick.bid_price > 0: price = tick.bid_price
            
            if price > 0:
                print(f"   >> {symbol}: {price:,.0f} Vol: {tick.last_volume:,}", end="\r")
                
                if target:
                    # Simple alert logic
                    if (target > 0 and price >= target) or (target < 0 and price <= abs(target)):
                        print(f"\n🚨  [ALERT] {symbol} hit target {abs(target)}! Current: {price}")
                        stop_event.set()

        ws_client = DNSEWebSocketClient(investor_id=investor_id, jwt_token=jwt, on_tick=on_tick)
        ws_client.connect()
        ws_client.subscribe(symbol)
        
        try:
            if target:
                await stop_event.wait()
            else:
                while True: await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            ws_client.disconnect()

    # --- SKILL 2: TRADE ---
    async def skill_trade(self):
        if not self.args.symbol or not self.args.price or not self.args.qty:
            logger.error("Usage: trade --symbol <SYM> --price <PRICE> --qty <QTY> [--action buy|sell]")
            return

        action = self.args.action if self.args.action in ['buy', 'sell'] else 'buy'
        symbol = self.args.symbol.upper()
        price = float(self.args.price)
        qty = int(self.args.qty)
        account_alias = self.args.account or "rocket"
        account_no = ACCOUNTS.get(account_alias, account_alias)

        logger.info(f"💸  [TRADE] Preparing {action.upper()} {qty} {symbol} @ {price} on {account_alias}...")
        
        client = await self.get_client(account_alias)
        
        # Auth Headers with Trading Token
        await client._auth_provider.ensure_trading_token()
        headers = client._auth_provider.get_auth_headers(include_trading_token=True)

        side = "NB" if action == 'buy' else "NS"
        condition = f"price <= {price}" if side == "NB" else f"price >= {price}"
        expire_time = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT07:30:00.000Z')

        payload = {
            "condition": condition,
            "targetOrder": {
                "quantity": qty,
                "side": side,
                "price": price,
                "loanPackageId": LOAN_PACKAGE_ID,
                "orderType": "LO"
            },
            "symbol": symbol,
            "props": {"stopPrice": price, "marketId": "UNDERLYING"},
            "accountNo": account_no,
            "category": "STOP",
            "timeInForce": {"expireTime": expire_time, "kind": "GTD"}
        }

        async with client._session.post(CONDITIONAL_ORDER_URL, json=payload, headers=headers) as resp:
            if resp.status in [200, 201]:
                data = await resp.json()
                logger.info(f"✅  Order Placed! ID: {data.get('id')}")
            else:
                text = await resp.text()
                logger.error(f"❌  Failed: {text}")

    # --- SKILL 3: AUDIT ---
    async def skill_audit(self):
        logger.info("📊  [AUDIT] Fetching positions for all accounts...")
        
        total_pnl = 0.0
        
        for alias, acc_no in ACCOUNTS.items():
            client = await self.get_client(alias)
            headers = client._auth_provider.get_auth_headers()
            
            # Fetch Deals
            async with client._session.get(DEAL_SERVICE_URL, params={"accountNo": acc_no}, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    deals = data.get('deals', [])
                    if deals:
                        print(f"\nAccount: {alias} ({acc_no})")
                        print(f"{ 'Symbol':<10} | {'Qty':<8} | {'Mkt Price':<10} | {'P/L':<15}")
                        print("-" * 50)
                        for d in deals:
                            pnl = float(d.get('unrealizedProfit', 0))
                            total_pnl += pnl
                            print(f"{d.get('symbol'):<10} | {d.get('quantity'):<8} | {d.get('marketPrice'):<10} | {pnl:,.0f}")
                    else:
                        pass # Silent for empty accounts
                else:
                    logger.warning(f"Failed to fetch deals for {alias}")

        print(f"\n{'-'*50}")
        print(f"💰  TOTAL P/L across accounts: {total_pnl:,.0f} VND")
        print(f"{'-'*50}")

    # --- SKILL 4: PANIC (STKILL) ---
    async def skill_panic(self):
        logger.warning("🚨  [PANIC] Initiating Kill Switch for ALL active orders...")
        
        # Ensure we have OTP
        if not self.otp_val:
            self.get_otp()

        for alias, acc_no in ACCOUNTS.items():
            client = await self.get_client(alias)
            # Need trading token
            await client._auth_provider.ensure_trading_token()
            headers = client._auth_provider.get_auth_headers(include_trading_token=True)
            
            # List Orders
            async with client._session.get(CONDITIONAL_ORDER_URL, params={"accountNo": acc_no}, headers=headers) as resp:
                if resp.status != 200: continue
                data = await resp.json()
                
                active_orders = [o for o in data.get('orders', []) if o.get('status') in ["WAIT_TRIGGER", "NEW", "PENDING", "SENT"]]
                
                if not active_orders:
                    logger.info(f"No active orders on {alias}.")
                    continue
                
                logger.info(f"Killing {len(active_orders)} orders on {alias}...")
                
                for order in active_orders:
                    url = f"{CONDITIONAL_ORDER_URL}/{order.get('id')}/cancel"
                    async with client._session.patch(url, headers=headers) as c_resp:
                        if c_resp.status == 200:
                            logger.info(f"  -> Killed order {order.get('id')}")
                        else:
                            logger.error(f"  -> Failed to kill {order.get('id')}")

    async def run(self):
        try:
            if self.args.skill == 'monitor':
                await self.skill_monitor()
            elif self.args.skill == 'trade':
                await self.skill_trade()
            elif self.args.skill == 'audit':
                await self.skill_audit()
            elif self.args.skill == 'panic':
                await self.skill_panic()
            else:
                print("Unknown skill. Use --help.")
        finally:
            await self.cleanup()

def main():
    parser = argparse.ArgumentParser(description="DNSE Skills Agent")
    subparsers = parser.add_subparsers(dest='skill', required=True)

    # Monitor
    p_mon = subparsers.add_parser('monitor', help='Watch a symbol')
    p_mon.add_argument('symbol', help='Symbol to watch')
    p_mon.add_argument('--price', help='Alert price target')
    p_mon.add_argument('--otp', help='OTP (not usually needed for monitor)')

    # Trade
    p_trade = subparsers.add_parser('trade', help='Execute a trade')
    p_trade.add_argument('action', choices=['buy', 'sell'], help='Action')
    p_trade.add_argument('symbol', help='Symbol')
    p_trade.add_argument('price', help='Price')
    p_trade.add_argument('qty', help='Quantity')
    p_trade.add_argument('--account', default='rocket', help='Account alias')
    p_trade.add_argument('--otp', help='Smart OTP')

    # Audit
    p_audit = subparsers.add_parser('audit', help='Check P/L positions')
    p_audit.add_argument('--otp', help='OTP (not usually needed for audit)')

    # Panic
    p_panic = subparsers.add_parser('panic', help='Cancel ALL active orders')
    p_panic.add_argument('--otp', help='Smart OTP')

    args = parser.parse_args()
    
    agent = SkillsAgent(args)
    asyncio.run(agent.run())

if __name__ == "__main__":
    main()
