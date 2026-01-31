import asyncio
import os
import sys
import aiohttp

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.getcwd()))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from dnse_trading.rest.client import DNSEHttpClient

async def check():
    username = os.environ.get("DNSE_USERNAME")
    password = os.environ.get("DNSE_PASSWORD")
    # Second account ID from previous listing
    account_no = "0001031199"
    
    client = DNSEHttpClient(username=username, password=password, account_no=account_no)
    await client.connect()
    
    # Try account-specific endpoint
    url = f"https://api.dnse.com.vn/order-service/accounts/{account_no}/loan-packages"
    headers = client._auth_provider.get_auth_headers()
    
    print(f"Fetching loan packages for {account_no}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            text = await response.text()
            print(f"Response: {text}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
