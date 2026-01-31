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

async def main():
    username = os.environ.get("DNSE_USERNAME")
    password = os.environ.get("DNSE_PASSWORD")
    # RocketX Account
    account_no = "0001031199"
    
    client = DNSEHttpClient(username=username, password=password, account_no=account_no)
    
    try:
        await client.connect()
        
        # Endpoint: /deal-service/deals?accountNo=...
        url = "https://api.dnse.com.vn/deal-service/deals"
        params = {"accountNo": account_no}
        
        # We need to manually construct this request as it's not in the standard client
        headers = client._auth_provider.get_auth_headers()
        
        print(f"Fetching DEALS for {account_no}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                status = response.status
                print(f"Status: {status}")
                if status == 200:
                    data = await response.json()
                    deals = data.get('deals', [])
                    print(f"Found {len(deals)} deals.")
                    
                    if deals:
                        print("DEBUG: Raw Deal[0]:", deals[0]) # Debug first deal
                        print(f"{'ID':<10} | {'Symbol':<8} | {'Qty':<8} | {'Cost':<10} | {'Mkt Price':<10} | {'P/L':<12}")
                        print("-" * 70)
                        for d in deals:
                            # Parse fields based on documentation summary
                            deal_id = d.get('id', 'N/A')
                            sym = d.get('symbol', 'N/A')
                            qty = d.get('quantity', 0)
                            cost = d.get('costPrice', 0)
                            mkt = d.get('marketPrice', 0)
                            pnl = d.get('unrealizedProfit', 0)
                            
                            print(f"{deal_id:<10} | {sym:<8} | {qty:<8} | {cost:<10} | {mkt:<10} | {pnl:<12}")
                else:
                    text = await response.text()
                    print(f"Error: {text}")

    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
