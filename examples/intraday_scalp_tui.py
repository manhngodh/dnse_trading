#!/usr/bin/env python3
"""
Intraday Scalping TUI (Bollinger Bands)
---------------------------------------
A Terminal User Interface for the Intraday Scalping Bot.
Displays real-time market data, strategy indicators, and signals.

Market: T+2.5 (Vietnam)
Mode: Paper Trading (Simulation)
"""

import asyncio
import os
import logging
import sys
import statistics
from collections import deque
from decimal import Decimal
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

# Configure logging to file to avoid messing up TUI
logging.basicConfig(
    level=logging.INFO,
    filename="intraday_scalp_tui.log",
    filemode="w",
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("IntradayScalpTUI")

# Load environment variables
try:
    from dotenv import load_dotenv
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv()
except ImportError:
    pass

# Add parent path to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dnse_trading.rest.client import DNSEHttpClient
from dnse_trading.websocket.client import DNSEWebSocketClient
from dnse_trading.common.types import DNSEMarketDataTick, DNSEOrderBookEntry

# Configuration
USERNAME = os.environ.get("DNSE_USERNAME")
PASSWORD = os.environ.get("DNSE_PASSWORD")
ACCOUNT_NO = os.environ.get("DNSE_ACCOUNT_NO")
SYMBOL = "VND"

# Strategy Parameters
WINDOW_SIZE = 20
STD_DEV_MULTIPLIER = 2.0
PAPER_TRADING = True

class ScalpTUI:
    def __init__(self):
        self.http_client = DNSEHttpClient(username=USERNAME, password=PASSWORD, account_no=ACCOUNT_NO)
        self.ws_client = None
        
        # Market Data State
        self.last_price = Decimal("0")
        self.last_vol = 0
        self.bids: list[DNSEOrderBookEntry] = []
        self.asks: list[DNSEOrderBookEntry] = []
        
        # Strategy State
        self.price_history = deque(maxlen=WINDOW_SIZE)
        self.upper_band = Decimal("0")
        self.lower_band = Decimal("0")
        self.sma = Decimal("0")
        self.position = 0
        self.avg_price = Decimal("0")
        
        # UI State
        self.last_update = datetime.now()
        self.logs = deque(maxlen=10) # Show last 10 logs in UI
        
        logger.info(f"Initialized Scalp TUI for {SYMBOL}")

    def log_ui(self, message: str):
        """Add message to UI logs and file logs."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")
        logger.info(message)

    async def start(self):
        try:
            # Connect
            self.log_ui("Connecting HTTP...")
            await self.http_client.connect()
            account = await self.http_client.get_account_info()
            investor_id = account.get("investorId")
            jwt = self.http_client._auth_provider.jwt_token
            self.log_ui(f"Connected: {account.get('name')}")
            
            # WebSocket
            self.ws_client = DNSEWebSocketClient(
                investor_id=investor_id,
                jwt_token=jwt,
                on_tick=self.on_tick,
                on_connected=self.on_ws_connected,
                on_disconnected=self.on_ws_disconnected
            )
            self.ws_client.connect()
            
            # Start UI Loop
            console = Console()
            with Live(self.generate_layout(), refresh_per_second=4, screen=True) as live:
                while True:
                    live.update(self.generate_layout())
                    await asyncio.sleep(0.25)
                    
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"Error: {e}")
        finally:
            if self.ws_client: self.ws_client.disconnect()
            if self.http_client._session and not self.http_client._session.closed:
                 await self.http_client._session.close()

    def on_ws_connected(self):
        self.log_ui("WebSocket Connected")
        if self.ws_client:
            self.ws_client.subscribe(SYMBOL)

    def on_ws_disconnected(self):
        self.log_ui("WebSocket Disconnected")

    def on_tick(self, tick: DNSEMarketDataTick):
        self.last_update = datetime.now()
        
        if tick.symbol != SYMBOL:
            return

        if tick.last_price > 0:
            self.last_price = tick.last_price
            self.last_vol = tick.last_volume
            self.update_strategy(tick.last_price)

        # Update Order Book if available
        if tick.bids: self.bids = tick.bids
        if tick.asks: self.asks = tick.asks

    def update_strategy(self, price: Decimal):
        """Calculate indicators and check signals."""
        self.price_history.append(float(price))
        
        if len(self.price_history) >= WINDOW_SIZE:
            sma_val = statistics.mean(self.price_history)
            stdev = statistics.stdev(self.price_history)
            self.sma = Decimal(f"{sma_val:.2f}")
            self.upper_band = Decimal(f"{sma_val + (stdev * STD_DEV_MULTIPLIER):.2f}")
            self.lower_band = Decimal(f"{sma_val - (stdev * STD_DEV_MULTIPLIER):.2f}")
            
            # Check Signals
            if price <= self.lower_band:
                self.execute_signal("BUY", price, "Price <= Lower Band")
            elif price >= self.upper_band:
                self.execute_signal("SELL", price, "Price >= Upper Band")

    def execute_signal(self, side: str, price: Decimal, reason: str):
        if side == "BUY" and self.position == 0:
            self.position = 100
            self.avg_price = price
            self.log_ui(f"[bold green]BUY SIGNAL[/] @ {price} ({reason})")
            
        elif side == "SELL" and self.position > 0:
            pnl = (price - self.avg_price) * self.position
            self.position = 0
            self.avg_price = Decimal("0")
            self.log_ui(f"[bold red]SELL SIGNAL[/] @ {price} | PnL: {pnl} ({reason})")

    def generate_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="upper", ratio=1),
            Layout(name="lower", size=10)
        )
        layout["upper"].split_row(
            Layout(name="market_data"),
            Layout(name="strategy")
        )
        
        # Header
        header_text = f"DNSE SCALPER TUI - {SYMBOL} | {datetime.now().strftime('%H:%M:%S')}"
        layout["header"].update(Panel(Align.center(header_text, vertical="middle"), style="bold white on blue"))
        
        # Market Data (Order Book)
        ob_table = Table(title="Order Book", expand=True)
        ob_table.add_column("Bid Vol", justify="right", style="green")
        ob_table.add_column("Bid", justify="right", style="green")
        ob_table.add_column("Ask", justify="left", style="red")
        ob_table.add_column("Ask Vol", justify="left", style="red")
        
        for i in range(10):
            bid = self.bids[i] if i < len(self.bids) else None
            ask = self.asks[i] if i < len(self.asks) else None
            ob_table.add_row(
                str(bid.quantity) if bid else "",
                str(bid.price) if bid else "",
                str(ask.price) if ask else "",
                str(ask.quantity) if ask else ""
            )
            
        layout["market_data"].update(Panel(ob_table, title="Market Depth"))
        
        # Strategy Panel
        strat_text = Text()
        strat_text.append(f"\nLast Price: ", style="bold")
        strat_text.append(f"{self.last_price}\n", style="bold yellow")
        
        strat_text.append(f"\nIndicators (Window {WINDOW_SIZE}):\n", style="underline")
        strat_text.append(f"Upper Band: {self.upper_band}\n", style="red")
        strat_text.append(f"SMA       : {self.sma}\n", style="cyan")
        strat_text.append(f"Lower Band: {self.lower_band}\n", style="green")
        
        strat_text.append(f"\nPosition (Paper):\n", style="underline")
        strat_text.append(f"Holding   : {self.position}\n")
        strat_text.append(f"Avg Price : {self.avg_price}\n")
        
        if self.position > 0 and self.last_price > 0:
            unrealized = (self.last_price - self.avg_price) * self.position
            color = "green" if unrealized >= 0 else "red"
            strat_text.append(f"Unr. PnL  : {unrealized:.2f}\n", style=f"bold {color}")

        layout["strategy"].update(Panel(Align.center(strat_text), title="Strategy Status"))
        
        # Logs
        log_text = "\n".join(self.logs)
        layout["lower"].update(Panel(log_text, title="Live Logs"))

        return layout

async def main():
    tui = ScalpTUI()
    await tui.start()

if __name__ == "__main__":
    asyncio.run(main())
