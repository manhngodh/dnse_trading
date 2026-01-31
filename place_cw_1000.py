import asyncio
import os
import sys
from decimal import Decimal
from datetime import datetime, timedelta

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.getcwd()))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from dnse_trading.rest.client import DNSEHttpClient

def get_otp():
    print("Please enter your Smart OTP:")
    return input().strip()

async def place_order():
    username = os.environ.get("DNSE_USERNAME")
    password = os.environ.get("DNSE_PASSWORD")
    account_no = "0001031199"
    symbol = "CHPG2602"
    price = 1250 # 1.25 * 1000
    quantity = 1000
    
    client = DNSEHttpClient(
        username=username, 
        password=password, 
        account_no=account_no,
        otp_callback=get_otp
    )
    
    try:
        await client.connect()
        
        # We need the trading token
        await client._auth_provider.ensure_trading_token()
        headers = client._auth_provider.get_auth_headers(include_trading_token=True)
        
        # Conditional Order API Endpoint
        url = "https://api.dnse.com.vn/conditional-order-api/v1/orders"
        
        # Expiry time (tomorrow)
        expire_time = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT07:30:00.000Z')
        
        payload = {
            "condition": f"price <= {price}",
            "targetOrder": {
                "quantity": quantity,
                "side": "NB",
                "price": price,
                "loanPackageId": 1775,
                "orderType": "LO"
            },
            "symbol": symbol,
            "props": {
                "stopPrice": price,
                "marketId": "UNDERLYING"
            },
            "accountNo": account_no,
            "category": "STOP",
            "timeInForce": {
                "expireTime": expire_time,
                "kind": "GTD"
            }
        }
        
        print(f"Placing Conditional Order for {symbol} (1000 units) on {account_no}...")
        
        async with client._session.post(url, json=payload, headers=headers) as response:
            status = response.status
            text = await response.text()
            print(f"Response Status: {status}")
            print(f"Response Text: {text}")
            
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(place_order())
