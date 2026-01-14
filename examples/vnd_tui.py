#!/usr/bin/env python3
"""
VND Order Book TUI

Displays real-time order book for VND using Rich.
"""
import asyncio
import os
import logging
import sys
from decimal import Decimal
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align

# Configure logging to file (to not mess up TUI)
logging.basicConfig(
    level=logging.INFO,
    filename="vnd_tui.log",
    filemode="w",
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VND_TUI")

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
from dnse_trading.common.types import DNSEMarketDataTick, DNSEOrderBookEntry

USERNAME = os.environ.get("DNSE_USERNAME")
PASSWORD = os.environ.get("DNSE_PASSWORD")
ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO")
SYMBOL = "VND"

class VNDOrderBookTUI:
    def __init__(self):
        self.http_client = DNSEHttpClient(username=USERNAME, password=PASSWORD, account_no=ACCOUNT_NO)
        self.ws_client = None
        self.last_trade_price = Decimal(0)
        self.last_trade_vol = 0
        self.bids: list[DNSEOrderBookEntry] = []
        self.asks: list[DNSEOrderBookEntry] = []
        self.last_update = datetime.now()

    def generate_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Header
        header_text = f"DNSE Market Data - {SYMBOL}"
        if self.last_trade_price > 0:
            header_text += f" | Last: {self.last_trade_price} ({self.last_trade_vol})"
        layout["header"].update(Panel(Align.center(header_text), style="bold white on blue"))
        
        # Body (Order Book)
        table = Table(title="Order Book", expand=True)
        table.add_column("Bid Vol", justify="right", style="green")
        table.add_column("Bid Price", justify="right", style="green")
        table.add_column("Ask Price", justify="left", style="red")
        table.add_column("Ask Vol", justify="left", style="red")
        
        # Merge bids/asks for display (up to 10 levels)
        max_rows = max(len(self.bids), len(self.asks))
        for i in range(max(10, max_rows)): # Show at least 10 rows if possible, or max available
            bid = self.bids[i] if i < len(self.bids) else None
            ask = self.asks[i] if i < len(self.asks) else None
            
            b_vol = str(bid.quantity) if bid else ""
            b_price = str(bid.price) if bid else ""
            a_price = str(ask.price) if ask else ""
            a_vol = str(ask.quantity) if ask else ""
            
            if bid or ask:
                table.add_row(b_vol, b_price, a_price, a_vol)

        layout["body"].update(Panel(Align.center(table)))
        
        # Footer
        layout["footer"].update(Panel(f"Last Update: {self.last_update.strftime('%H:%M:%S')} | Log: vnd_tui.log"))
        
        return layout

    async def start(self):
        try:
            await self.http_client.connect()
            account = await self.http_client.get_account_info()
            investor_id = account.get("investorId")
            jwt = self.http_client._auth_provider.jwt_token
            
            self.ws_client = DNSEWebSocketClient(
                investor_id=investor_id,
                jwt_token=jwt,
                on_tick=self.on_tick
            )
            self.ws_client.connect()
            self.ws_client.subscribe(SYMBOL)
            
            console = Console()
            with Live(self.generate_layout(), refresh_per_second=10, screen=True) as live:
                while True:
                    live.update(self.generate_layout())
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            if self.ws_client: self.ws_client.disconnect()
            await self.http_client.disconnect()

    def on_tick(self, tick: DNSEMarketDataTick):
        self.last_update = datetime.now()
        
        if tick.last_price > 0:
            self.last_trade_price = tick.last_price
            self.last_trade_vol = tick.last_volume
        
        if tick.bids:
            self.bids = tick.bids
        if tick.asks:
            self.asks = tick.asks

async def main():
    tui = VNDOrderBookTUI()
    await tui.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
