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
from dnse_trading.common.enums import DNSEOrderSide, DNSEOrderType

def get_otp():
    print("Please enter your Smart OTP:")
    return input().strip()

async def place_order():
    username = os.environ.get("DNSE_USERNAME")
    password = os.environ.get("DNSE_PASSWORD")
    account_no = "0001031199"
    symbol = "CHPG2602"
    
    # Try Market Price (MP)
    quantity = 100
    
    client = DNSEHttpClient(
        username=username, 
        password=password, 
        account_no=account_no,
        otp_callback=get_otp
    )
    
    try:
        await client.connect()
        print(f"Connected to account {account_no}")
        print(f"Placing BUY MARKET Order: {quantity} {symbol}...")
        
        # Using loanPackageId 1775 (Cash) 
        response = await client.place_order(
            symbol=symbol,
            side=DNSEOrderSide.BUY,
            order_type=DNSEOrderType.MARKET, # MP
            price=Decimal("0"),
            quantity=quantity,
            loan_package_id=1775
        )
        
        print("\nOrder Placed Successfully!")
        print(f"Order ID: {response.get('id')}")
        
    except Exception as e:
        print(f"\nError placing order: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(place_order())
