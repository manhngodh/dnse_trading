#!/usr/bin/env python3
"""
DNSE Trading Example - Basic Usage

This script demonstrates how to use the DNSE trading adapter
for basic operations like authentication, account info, and order placement.

Prerequisites:
    pip install aiohttp paho-mqtt

Usage:
    python example_usage.py
"""
import asyncio
import os
import logging
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    from dotenv import load_dotenv
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv()
except ImportError:
    pass

# Add parent path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dnse_trading.common.enums import DNSEOrderSide, DNSEOrderType
from dnse_trading.rest.client import DNSEHttpClient
from dnse_trading.websocket.client import DNSEWebSocketClient
from dnse_trading.common.types import DNSEMarketDataTick


# ============================================================================
# Configuration
# ============================================================================

# Set these from environment variables or replace with your credentials
USERNAME = os.environ.get("DNSE_USERNAME", "your_username")
PASSWORD = os.environ.get("DNSE_PASSWORD", "your_password")
ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO", "your_account_no")


# ============================================================================
# OTP Callback (for trading operations)
# ============================================================================

def get_otp_from_user() -> str:
    """
    Prompt user for OTP.
    
    In production, you might:
    - Read from a file that's updated by your mobile app
    - Use a TOTP library if Smart OTP is TOTP-compatible
    - Receive via email and parse
    """
    return input("Enter Smart OTP from DNSE app: ").strip()


# ============================================================================
# Example Functions
# ============================================================================

async def example_account_info():
    """Example: Get account information."""
    print("\n" + "=" * 50)
    print("📋 ACCOUNT INFORMATION")
    print("=" * 50)
    
    client = DNSEHttpClient(
        username=USERNAME,
        password=PASSWORD,
        account_no=ACCOUNT_NO,
    )
    
    try:
        await client.connect()
        
        # Get account info
        account = await client.get_account_info()
        print(f"Investor ID: {account.get('investorId')}")
        print(f"Name: {account.get('name')}")
        print(f"Custody Code: {account.get('custodyCode')}")
        print(f"Email: {account.get('email')}")
        print(f"Mobile: {account.get('mobile')}")
        
        # Get sub-accounts
        try:
            sub_accounts = await client.get_sub_accounts()
            print(f"\nSub-accounts: {len(sub_accounts)}")
            for acc in sub_accounts[:5]:  # Show first 5
                print(f"  - {acc.get('accountNo')}: {acc.get('accountType')}")
        except Exception as e:
            print(f"Could not get sub-accounts: {e}")
        
    finally:
        await client.disconnect()


async def example_market_data():
    """Example: Subscribe to real-time market data."""
    print("\n" + "=" * 50)
    print("📈 REAL-TIME MARKET DATA")
    print("=" * 50)
    
    client = DNSEHttpClient(
        username=USERNAME,
        password=PASSWORD,
        account_no=ACCOUNT_NO,
    )
    
    ticks_received = []
    
    def on_tick(tick: DNSEMarketDataTick):
        """Handle incoming tick."""
        ticks_received.append(tick)
        print(f"[{tick.timestamp}] {tick.symbol}: "
              f"Last={tick.last_price} Vol={tick.last_volume} "
              f"Bid={tick.bid_price} Ask={tick.ask_price}")
    
    try:
        await client.connect()
        
        # Get investor ID for WebSocket auth
        account = await client.get_account_info()
        investor_id = account.get("investorId")
        jwt_token = client._auth_provider.jwt_token
        
        # Create WebSocket client
        ws_client = DNSEWebSocketClient(
            investor_id=investor_id,
            jwt_token=jwt_token,
            on_tick=on_tick,
        )
        
        # Connect and subscribe
        ws_client.connect()
        ws_client.subscribe("VND")
        
        print("Subscribed to VND. Waiting for ticks...")
        print("(Press Ctrl+C to stop)\n")
        
        # Wait for some ticks (or timeout)
        try:
            await asyncio.sleep(30)  # Listen for 30 seconds
        except KeyboardInterrupt:
            pass
        
        ws_client.disconnect()
        print(f"\nReceived {len(ticks_received)} ticks")
        
    finally:
        await client.disconnect()


async def example_trading():
    """Example: Place and cancel an order."""
    print("\n" + "=" * 50)
    print("💹 TRADING OPERATIONS")
    print("=" * 50)
    
    client = DNSEHttpClient(
        username=USERNAME,
        password=PASSWORD,
        account_no=ACCOUNT_NO,
        otp_callback=get_otp_from_user,
    )
    
    try:
        await client.connect()
        
        # Get buying power first
        print("\n📊 Checking buying power for VNM...")
        try:
            pp = await client.get_buying_power(symbol="VNM")
            print(f"Max Buy Qty: {pp.get('maxBuyQty')}")
            print(f"Max Sell Qty: {pp.get('maxSellQty')}")
            print(f"Available Cash: {pp.get('availableCash')}")
        except Exception as e:
            print(f"Could not get buying power: {e}")
        
        # Request trading token (requires OTP)
        print("\n🔐 Requesting trading token...")
        try:
            await client.request_trading_token()
            print("✅ Trading token obtained!")
        except Exception as e:
            print(f"❌ Failed to get trading token: {e}")
            print("Trading operations require OTP verification.")
            return
        
        # Example: Place a limit order (commented out for safety)
        print("\n📝 Order Placement Example (DRY RUN)")
        print("To actually place an order, uncomment the code below:")
        print("""
        response = await client.place_order(
            symbol="VNM",
            side=DNSEOrderSide.BUY,
            order_type=DNSEOrderType.LIMIT,
            price=Decimal("75000"),
            quantity=100,
        )
        print(f"Order ID: {response['id']}")
        print(f"Status: {response['orderStatus']}")
        """)
        
        # Get order book
        print("\n📖 Order Book:")
        try:
            orders = await client.get_orders()
            if orders:
                print(f"Found {len(orders)} orders")
                for order in orders[:5]:
                    print(f"  [{order.get('orderStatus')}] "
                          f"{order.get('side')} {order.get('quantity')} "
                          f"{order.get('symbol')} @ {order.get('price')}")
            else:
                print("No orders found")
        except Exception as e:
            print(f"Could not get orders: {e}")
        
        # Get holdings
        print("\n💼 Holdings:")
        try:
            holdings = await client.get_holdings()
            if holdings:
                print(f"Found {len(holdings)} holdings")
                for h in holdings[:10]:
                    print(f"  {h.get('symbol')}: {h.get('quantity')} shares "
                          f"@ {h.get('averagePrice')} avg")
            else:
                print("No holdings found")
        except Exception as e:
            print(f"Could not get holdings: {e}")
        
    finally:
        await client.disconnect()


async def example_derivatives():
    """Example: Derivative trading (VN30 Futures)."""
    print("\n" + "=" * 50)
    print("📉 DERIVATIVE TRADING (VN30 Futures)")
    print("=" * 50)
    
    client = DNSEHttpClient(
        username=USERNAME,
        password=PASSWORD,
        account_no=ACCOUNT_NO,
        otp_callback=get_otp_from_user,
    )
    
    try:
        await client.connect()
        
        # Get derivative positions
        print("\n📊 Derivative Positions:")
        try:
            positions = await client.get_derivative_positions()
            if positions:
                print(f"Found {len(positions)} positions")
                for pos in positions:
                    print(f"  {pos.get('symbol')}: {pos.get('quantity')} "
                          f"@ {pos.get('averagePrice')}")
            else:
                print("No derivative positions")
        except Exception as e:
            print(f"Could not get positions: {e}")
        
        print("\n📝 Derivative Order Example (DRY RUN)")
        print("To place a VN30F order, use:")
        print("""
        response = await client.place_derivative_order(
            symbol="VN30F2501",  # January 2025 contract
            side=DNSEOrderSide.BUY,
            order_type=DNSEOrderType.LIMIT,
            price=Decimal("1250.5"),
            quantity=1,
        )
        """)
        
    finally:
        await client.disconnect()


# ============================================================================
# Main
# ============================================================================

async def main():
    print("=" * 50)
    print("🚀 DNSE TRADING ADAPTER EXAMPLES")
    print("=" * 50)
    
    if USERNAME == "your_username":
        print("\n⚠️  Please set your credentials:")
        print("  export DNSE_USERNAME='your_username'")
        print("  export DNSE_PASSWORD='your_password'")
        print("  export DNSE_ACCOUNT_NO='your_account_no'")
        return
    
    # Run examples
    await example_account_info()
    
    # Uncomment to test other examples:
    await example_market_data()
    # await example_trading()
    # await example_derivatives()
    
    print("\n" + "=" * 50)
    print("✅ Examples completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
