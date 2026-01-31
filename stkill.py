#!/usr/bin/env python3
import asyncio
import os
import sys
import argparse
import logging
import aiohttp

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from dnse_trading.rest.client import DNSEHttpClient

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("STKILL")

# Accounts to check
ACCOUNTS = {
    "SpaceX": "0001010274",
    "RocketX": "0001031199"
}

CONDITIONAL_ORDER_URL = "https://api.dnse.com.vn/conditional-order-api/v1/orders"

async def kill_orders(account_alias, account_no, username, password):
    logger.info(f"\nScanning {account_alias} ({account_no})...")
    
    # We need a client per account context ideally, or just one auth client 
    # but requests need correct accountNo param/header if applicable.
    # The conditional order list usually filters by accountNo query param.
    
    client = DNSEHttpClient(username=username, password=password, account_no=account_no)
    
    try:
        await client.connect()
        
        # Get Headers (Auth)
        # Note: Cancelling usually requires Trading Token
        await client._auth_provider.ensure_trading_token()
        headers = client._auth_provider.get_auth_headers(include_trading_token=True)
        
        # 1. LIST ORDERS
        params = {
            "accountNo": account_no,
            "status": "PENDING,WAIT_TRIGGER,SENT,NEW" # Guessing common statuses, or fetch all and filter
        }
        
        # Fetching all (no status filter) often safer to see everything
        async with client._session.get(CONDITIONAL_ORDER_URL, params={"accountNo": account_no}, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                logger.error(f"Failed to list orders: {text}")
                return

            data = await response.json()
            orders = data.get('orders', [])
            
            # Filter for active orders
            # Statuses usually: WAIT_TRIGGER, TRIGGERED, SENT, ...
            # We want to kill anything not FILLED, CANCELLED, REJECTED, EXPIRED
            active_statuses = ["WAIT_TRIGGER", "NEW", "PENDING", "SENT"]
            active_orders = [o for o in orders if o.get('status') in active_statuses]
            
            if not active_orders:
                logger.info(f"No active orders found on {account_alias}.")
                return
            
            logger.info(f"Found {len(active_orders)} active orders on {account_alias}. Killing...")
            
            # 2. KILL ORDERS
            for order in active_orders:
                order_id = order.get('id')
                symbol = order.get('symbol')
                price = order.get('targetOrder', {}).get('price')
                side = order.get('targetOrder', {}).get('side')
                
                cancel_url = f"{CONDITIONAL_ORDER_URL}/{order_id}/cancel"
                
                logger.info(f" -> Killing {side} {symbol} @ {price} (ID: {order_id})...")
                
                # Use PATCH as per documentation
                async with client._session.patch(cancel_url, headers=headers) as cancel_resp:
                    if cancel_resp.status == 200:
                        logger.info("    ✅ Killed.")
                    else:
                        text = await cancel_resp.text()
                        logger.error(f"    ❌ Failed: {text}")
                        
    except Exception as e:
        logger.error(f"Error on {account_alias}: {e}")
    finally:
        await client.disconnect()

async def main():
    parser = argparse.ArgumentParser(description="STKILL - Stop/Kill All Active Conditional Orders")
    parser.add_argument('--account', help="Specific account alias to kill (spacex, rocket)")
    parser.add_argument('--otp', help="Smart OTP")
    args = parser.parse_args()

    username = os.environ.get("DNSE_USERNAME")
    password = os.environ.get("DNSE_PASSWORD")
    
    # Setup OTP callback globally if provided
    # DNSEHttpClient takes a callback. We need to handle this gracefully if running parallel.
    # For simplicity, we'll ask once if not provided.
    
    otp_val = args.otp
    if not otp_val:
        print("Please enter your Smart OTP for STKILL verification:")
        otp_val = input().strip()
    
    # Hack: Monkey patch the OTP callback logic for the instances we create
    # or just pass a lambda.
    otp_callback = lambda: otp_val

    # Inject the OTP into the client instances we create
    # Actually, DNSEHttpClient.__init__ takes otp_callback.
    
    target_accounts = ACCOUNTS.items()
    if args.account:
        # Filter if specific account requested
        target_accounts = [(k, v) for k, v in ACCOUNTS.items() if k.lower() == args.account.lower() or k.lower().startswith(args.account.lower())]

    print(f"Executing STKILL on: {', '.join([k for k,v in target_accounts])}")
    
    for alias, acc_no in target_accounts:
        # Need to create a new client for each to be safe with context/session
        # We pass the same OTP callback
        # We need to recreate the client or it will be fresh.
        # But we need to pass the OTP value.
        
        # We can't pass `otp_val` directly to constructor, it needs a callback.
        # So we pass `lambda: otp_val`
        
        await kill_orders(alias, acc_no, username, password)

if __name__ == "__main__":
    asyncio.run(main())
