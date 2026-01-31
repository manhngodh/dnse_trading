#!/usr/bin/env python3
import asyncio
import os
import sys
import argparse
from decimal import Decimal
from datetime import datetime, timedelta
import logging

# Add parent directory to sys.path to allow importing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from dnse_trading.rest.client import DNSEHttpClient
from dnse_trading.common.enums import DNSEOrderSide

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("DNSE_CLI")

# Account Aliases
ACCOUNTS = {
    "spacex": "0001010274",
    "rocket": "0001031199",
    "primary": "0001010274", 
    "secondary": "0001031199"
}

# Known working configuration
LOAN_PACKAGE_ID = 1775 # "GD Tiền mặt"
CONDITIONAL_ORDER_URL = "https://api.dnse.com.vn/conditional-order-api/v1/orders"
DEAL_SERVICE_URL = "https://api.dnse.com.vn/deal-service/deals"

class DNSECLI:
    def __init__(self, args):
        self.args = args
        self.username = os.environ.get("DNSE_USERNAME")
        self.password = os.environ.get("DNSE_PASSWORD")
        self.account_no = ACCOUNTS.get(args.account, args.account) if args.account else ACCOUNTS["rocket"]
        self.otp = args.otp
        self.client = None

    def get_otp_callback(self):
        if self.otp:
            return self.otp
        print("Please enter your Smart OTP:")
        return input().strip()

    async def connect(self):
        self.client = DNSEHttpClient(
            username=self.username,
            password=self.password,
            account_no=self.account_no,
            otp_callback=self.get_otp_callback
        )
        await self.client.connect()
        # logger.info(f"Connected to account: {self.account_no}")

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()

    async def place_order(self):
        if not self.args.symbol or not self.args.price or not self.args.qty:
            logger.error("Error: --symbol, --price, and --qty are required for orders.")
            return

        side = "NB" if self.args.action == 'buy' else "NS"
        price = float(self.args.price)
        qty = int(self.args.qty)
        
        # Ensure Trading Token
        await self.client._auth_provider.ensure_trading_token()
        headers = self.client._auth_provider.get_auth_headers(include_trading_token=True)

        # Build Condition
        condition = f"price <= {price}" if side == "NB" else f"price >= {price}"
        
        # Expiry
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
            "symbol": self.args.symbol.upper(),
            "props": {
                "stopPrice": price,
                "marketId": "UNDERLYING"
            },
            "accountNo": self.account_no,
            "category": "STOP",
            "timeInForce": {
                "expireTime": expire_time,
                "kind": "GTD"
            }
        }

        logger.info(f"Placing {side} Order: {qty} {self.args.symbol} @ {price} on {self.account_no}...")
        
        async with self.client._session.post(CONDITIONAL_ORDER_URL, json=payload, headers=headers) as response:
            if response.status in [200, 201]:
                data = await response.json()
                logger.info(f"✅ SUCCESS! Order ID: {data.get('id')}")
            else:
                text = await response.text()
                logger.error(f"❌ FAILED (HTTP {response.status}): {text}")

    async def list_deals(self):
        headers = self.client._auth_provider.get_auth_headers()
        params = {"accountNo": self.account_no}
        
        logger.info(f"Fetching deals for {self.account_no}...")
        
        async with self.client._session.get(DEAL_SERVICE_URL, params=params, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                deals = data.get('deals', [])
                
                if not deals:
                    logger.info("No active deals found.")
                    return

                print(f"{'Symbol':<10} | {'Qty':<8} | {'Cost':<10} | {'Mkt Price':<10} | {'P/L':<12}")
                print("-" * 60)
                for d in deals:
                    sym = d.get('symbol', 'N/A')
                    # Use openQuantity or accumulateQuantity
                    qty = d.get('openQuantity') or d.get('accumulateQuantity', 0)
                    cost = d.get('costPrice', 0)
                    mkt = d.get('marketPrice', 0)
                    pnl = d.get('unrealizedProfit', 0)
                    
                    print(f"{sym:<10} | {qty:<8} | {cost:<10} | {mkt:<10} | {pnl:<12}")
            else:
                text = await response.text()
                logger.error(f"Error fetching deals: {text}")

    async def show_info(self):
        logger.info("Fetching Account Information...")
        try:
            # 1. Main Account Info
            account = await self.client.get_account_info()
            print(f"\n[ INVESTOR INFO ]")
            print(f"Name: {account.get('name')}")
            print(f"ID:   {account.get('investorId')}")
            print(f"Custody: {account.get('custodyCode')}")
            
            # 2. Sub-accounts
            sub_accounts = await self.client.get_sub_accounts()
            print(f"\n[ SUB-ACCOUNTS ]")
            # Handle the specific structure we saw earlier
            if isinstance(sub_accounts, dict) and 'accounts' in sub_accounts:
                sub_accounts = sub_accounts['accounts']
            
            for acc in sub_accounts:
                print(f"ID: {acc.get('id')} | Type: {acc.get('accountTypeName')} | Default: {'Yes' if acc.get('id') == self.account_no else 'No'}")

            # 3. Buying Power (for a symbol if provided, or default VND)
            symbol = self.args.symbol.upper() if self.args.symbol else "VND"
            logger.info(f"\nFetching Buying Power for {symbol} on {self.account_no}...")
            try:
                # Need trading token for PP sometimes or just headers
                pp = await self.client.get_buying_power(symbol=symbol, loan_package_id=LOAN_PACKAGE_ID)
                print(f"\n[ BUYING POWER - {symbol} ]")
                print(f"Available Cash: {pp.get('availableCash'):,.0f} VND")
                print(f"Max Buy Qty:    {pp.get('maxBuyQty'):,}")
                print(f"Max Sell Qty:   {pp.get('maxSellQty'):,}")
            except Exception as e:
                logger.error(f"Could not fetch buying power: {e}")

        except Exception as e:
            logger.error(f"Error fetching info: {e}")

    async def run(self):
        try:
            await self.connect()
            
            if self.args.action in ['buy', 'sell']:
                await self.place_order()
            elif self.args.action == 'deals':
                await self.list_deals()
            elif self.args.action == 'info':
                await self.show_info()
                
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            await self.disconnect()

def main():
    parser = argparse.ArgumentParser(description="DNSE Trading CLI")
    parser.add_argument('action', choices=['buy', 'sell', 'deals', 'info'], help="Action to perform")
    parser.add_argument('--symbol', help="Stock Symbol (e.g., VND)")
    parser.add_argument('--price', help="Order Price (Absolute VND)")
    parser.add_argument('--qty', help="Order Quantity")
    parser.add_argument('--account', default="rocket", help="Account alias (rocket, spacex) or ID")
    parser.add_argument('--otp', help="Smart OTP (optional, will prompt if missing)")
    
    args = parser.parse_args()
    
    cli = DNSECLI(args)
    asyncio.run(cli.run())

if __name__ == "__main__":
    main()
