"""
DNSE Data Client for NautilusTrader.

Provides real-time market data from DNSE via WebSocket.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Optional

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import Clock, MessageBus
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.data import QuoteTick, TradeTick, Bar, BarType
from nautilus_trader.model.enums import BookType, PriceType
from nautilus_trader.model.identifiers import ClientId, InstrumentId, Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Price, Quantity

from adapters.dnse.common.types import DNSEMarketDataTick
from adapters.dnse.config import DNSEDataClientConfig
from adapters.dnse.http.client import DNSEHttpClient
from adapters.dnse.websocket.client import DNSEWebSocketClient


_log = logging.getLogger(__name__)


class DNSEDataClient(LiveMarketDataClient):
    """
    DNSE Data Client for live market data.
    
    Connects to DNSE WebSocket for real-time price feeds and converts
    them to NautilusTrader data types.
    
    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        The event loop.
    client : DNSEHttpClient
        The HTTP client for account info.
    msgbus : MessageBus
        The message bus.
    cache : Cache  
        The cache.
    clock : Clock
        The clock.
    config : DNSEDataClientConfig
        The configuration.
    """
    
    VENUE = Venue("DNSE")
    
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client: DNSEHttpClient,
        msgbus: MessageBus,
        cache: Cache,
        clock: Clock,
        config: DNSEDataClientConfig,
    ):
        super().__init__(
            loop=loop,
            client_id=ClientId("DNSE"),
            venue=self.VENUE,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
        )
        
        self._http_client = client
        self._config = config
        self._ws_client: Optional[DNSEWebSocketClient] = None
        self._investor_id: Optional[str] = None
        
        # Track subscriptions
        self._subscribed_quote_ticks: set[InstrumentId] = set()
        self._subscribed_trade_ticks: set[InstrumentId] = set()
    
    async def _connect(self) -> None:
        """Connect to DNSE data feeds."""
        _log.info("Connecting DNSE data client...")
        
        # Connect HTTP client and get investor ID
        await self._http_client.connect()
        
        account_info = await self._http_client.get_account_info()
        self._investor_id = account_info.get("investorId")
        
        if not self._investor_id:
            raise RuntimeError("Failed to get investor ID from account info")
        
        # Create and connect WebSocket client
        jwt_token = self._http_client._auth_provider.jwt_token
        
        self._ws_client = DNSEWebSocketClient(
            investor_id=self._investor_id,
            jwt_token=jwt_token,
            on_tick=self._on_market_data_tick,
            on_connected=self._on_ws_connected,
            on_disconnected=self._on_ws_disconnected,
        )
        
        self._ws_client.connect()
        
        _log.info("DNSE data client connected")
    
    async def _disconnect(self) -> None:
        """Disconnect from DNSE data feeds."""
        _log.info("Disconnecting DNSE data client...")
        
        if self._ws_client is not None:
            self._ws_client.disconnect()
            self._ws_client = None
        
        await self._http_client.disconnect()
        
        self._subscribed_quote_ticks.clear()
        self._subscribed_trade_ticks.clear()
        
        _log.info("DNSE data client disconnected")
    
    async def _subscribe_quote_ticks(self, instrument_id: InstrumentId) -> None:
        """Subscribe to quote tick updates for an instrument."""
        if self._ws_client is None:
            _log.warning("WebSocket not connected, cannot subscribe")
            return
        
        symbol = self._instrument_id_to_symbol(instrument_id)
        self._ws_client.subscribe(symbol)
        self._subscribed_quote_ticks.add(instrument_id)
        
        _log.info(f"Subscribed to quote ticks for {instrument_id}")
    
    async def _subscribe_trade_ticks(self, instrument_id: InstrumentId) -> None:
        """Subscribe to trade tick updates for an instrument."""
        if self._ws_client is None:
            _log.warning("WebSocket not connected, cannot subscribe")
            return
        
        symbol = self._instrument_id_to_symbol(instrument_id)
        self._ws_client.subscribe(symbol)
        self._subscribed_trade_ticks.add(instrument_id)
        
        _log.info(f"Subscribed to trade ticks for {instrument_id}")
    
    async def _unsubscribe_quote_ticks(self, instrument_id: InstrumentId) -> None:
        """Unsubscribe from quote tick updates."""
        symbol = self._instrument_id_to_symbol(instrument_id)
        
        self._subscribed_quote_ticks.discard(instrument_id)
        
        # Only unsubscribe from WebSocket if not needed for trade ticks
        if instrument_id not in self._subscribed_trade_ticks:
            if self._ws_client is not None:
                self._ws_client.unsubscribe(symbol)
        
        _log.info(f"Unsubscribed from quote ticks for {instrument_id}")
    
    async def _unsubscribe_trade_ticks(self, instrument_id: InstrumentId) -> None:
        """Unsubscribe from trade tick updates."""
        symbol = self._instrument_id_to_symbol(instrument_id)
        
        self._subscribed_trade_ticks.discard(instrument_id)
        
        # Only unsubscribe from WebSocket if not needed for quote ticks
        if instrument_id not in self._subscribed_quote_ticks:
            if self._ws_client is not None:
                self._ws_client.unsubscribe(symbol)
        
        _log.info(f"Unsubscribed from trade ticks for {instrument_id}")
    
    def _on_market_data_tick(self, tick: DNSEMarketDataTick) -> None:
        """Handle incoming market data tick."""
        try:
            instrument_id = self._symbol_to_instrument_id(tick.symbol)
            
            # Generate quote tick if subscribed
            if instrument_id in self._subscribed_quote_ticks:
                quote_tick = self._create_quote_tick(tick, instrument_id)
                if quote_tick is not None:
                    self._handle_data(quote_tick)
            
            # Generate trade tick if subscribed
            if instrument_id in self._subscribed_trade_ticks:
                trade_tick = self._create_trade_tick(tick, instrument_id)
                if trade_tick is not None:
                    self._handle_data(trade_tick)
                    
        except Exception as e:
            _log.error(f"Error processing market data tick: {e}")
    
    def _create_quote_tick(
        self, 
        tick: DNSEMarketDataTick, 
        instrument_id: InstrumentId,
    ) -> Optional[QuoteTick]:
        """Create QuoteTick from DNSE tick data."""
        try:
            instrument = self._cache.instrument(instrument_id)
            if instrument is None:
                return None
            
            return QuoteTick(
                instrument_id=instrument_id,
                bid_price=Price(tick.bid_price, instrument.price_precision),
                ask_price=Price(tick.ask_price, instrument.price_precision),
                bid_size=Quantity(tick.bid_volume, 0),
                ask_size=Quantity(tick.ask_volume, 0),
                ts_event=int(tick.timestamp.timestamp() * 1e9),
                ts_init=self._clock.timestamp_ns(),
            )
        except Exception as e:
            _log.error(f"Failed to create quote tick: {e}")
            return None
    
    def _create_trade_tick(
        self, 
        tick: DNSEMarketDataTick, 
        instrument_id: InstrumentId,
    ) -> Optional[TradeTick]:
        """Create TradeTick from DNSE tick data."""
        try:
            instrument = self._cache.instrument(instrument_id)
            if instrument is None:
                return None
            
            # Skip if no last trade
            if tick.last_price <= 0 or tick.last_volume <= 0:
                return None
            
            from nautilus_trader.model.enums import AggressorSide
            
            return TradeTick(
                instrument_id=instrument_id,
                price=Price(tick.last_price, instrument.price_precision),
                size=Quantity(tick.last_volume, 0),
                aggressor_side=AggressorSide.NO_AGGRESSOR,
                trade_id=self._clock.timestamp_ns(),
                ts_event=int(tick.timestamp.timestamp() * 1e9),
                ts_init=self._clock.timestamp_ns(),
            )
        except Exception as e:
            _log.error(f"Failed to create trade tick: {e}")
            return None
    
    def _on_ws_connected(self) -> None:
        """Handle WebSocket connected event."""
        _log.info("DNSE WebSocket connected")
    
    def _on_ws_disconnected(self) -> None:
        """Handle WebSocket disconnected event."""
        _log.warning("DNSE WebSocket disconnected")
    
    def _instrument_id_to_symbol(self, instrument_id: InstrumentId) -> str:
        """Convert InstrumentId to DNSE symbol."""
        # Format: SYMBOL.DNSE -> SYMBOL
        return instrument_id.symbol.value
    
    def _symbol_to_instrument_id(self, symbol: str) -> InstrumentId:
        """Convert DNSE symbol to InstrumentId."""
        return InstrumentId.from_str(f"{symbol}.DNSE")
