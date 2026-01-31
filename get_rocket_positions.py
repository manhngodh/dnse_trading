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

async def main():
    username = os.environ.get("DNSE_USERNAME")
    password = os.environ.get("DNSE_PASSWORD")
    # Use a default, will switch dynamically
    account_no = "0000000000"
    
    client = DNSEHttpClient(username=username, password=password, account_no=account_no)
    
    try:
        await client.connect()
        
        print("Fetching account list...")
        sub_accounts_resp = await client.get_sub_accounts()
        
        # Handle response structure
        accounts = []
        if isinstance(sub_accounts_resp, dict):
            accounts = sub_accounts_resp.get('accounts', [])
        elif isinstance(sub_accounts_resp, list):
            accounts = sub_accounts_resp
            
        # Filter for Rocket accounts
        rocket_accounts = [
            acc for acc in accounts 
            if "Rocket" in str(acc.get('accountTypeName', ''))
        ]
        
        if not rocket_accounts:
            print("No accounts with 'Rocket' in type name found. Checking all accounts...")
            rocket_accounts = accounts

        print(f"Found {len(rocket_accounts)} target accounts.")

        for acc in rocket_accounts:
            acc_id = acc.get('id')
            acc_name = acc.get('accountTypeName')
            print(f"\n{'='*60}")
            print(f"ACCOUNT: {acc_id} ({acc_name})")
            print(f"{'='*60}")
            
            # Switch client to this account
            client._account_no = acc_id
            
            # 1. STOCK HOLDINGS
            print("\n--- Stock Holdings ---")
            try:
                holdings = await client.get_holdings()
                if not holdings:
                    print("No stock holdings.")
                else:
                    # Print table header
                    print(f"{'Symbol':<8} | {'Avail':<10} | {'Total':<10} | {'Avg Price':<12} | {'Mkt Price':<12} | {'P/L':<15}")
                    print("-" * 80)
                    
                    for h in holdings:
                        sym = h.get('symbol', 'N/A')
                        # Check API specific field names (usually camelCase)
                        avail = h.get('availableQuantity', 0)
                        total = h.get('quantity', 0)
                        avg_price = h.get('averagePrice', 0)
                        mkt_price = h.get('marketPrice', 0)
                        
                        # Calculate P/L if not provided
                        pnl = h.get('profitLoss')
                        if pnl is None and total > 0:
                            # Simple estimation
                            cost = total * avg_price
                            val = total * mkt_price
                            pnl = val - cost
                            
                        print(f"{sym:<8} | {avail:<10} | {total:<10} | {avg_price:<12} | {mkt_price:<12} | {pnl:<15}")
                        
            except Exception as e:
                print(f"Error fetching holdings: {e}")

            # 2. DERIVATIVE POSITIONS
            # Check if derivative account
            is_derivative = acc.get('derivativeAccount', False)
            if is_derivative:
                print("\n--- Derivative Positions ---")
                try:
                    positions = await client.get_derivative_positions()
                    if not positions:
                        print("No derivative positions.")
                    else:
                        print(f"{'Symbol':<10} | {'Side':<6} | {'Qty':<8} | {'Avg Price':<12} | {'Mkt Price':<12} | {'Floating P/L':<15}")
                        print("-" * 80)
                        for p in positions:
                            sym = p.get('seriesID') or p.get('symbol')
                            side = p.get('side') # Long/Short?
                            qty = p.get('quantity') or p.get('volume')
                            avg = p.get('averagePrice')
                            mkt = p.get('marketPrice')
                            pnl = p.get('floatingPL')
                            
                            print(f"{sym:<10} | {side:<6} | {qty:<8} | {avg:<12} | {mkt:<12} | {pnl:<15}")
                except Exception as e:
                    print(f"Error fetching derivatives: {e}")
            else:
                print("\n(Not a derivative account)")

    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
