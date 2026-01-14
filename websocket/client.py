"""
DNSE WebSocket client for real-time market data.

Uses MQTT over WebSocket to receive price updates.
"""
import asyncio
import json
import logging
import ssl
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    mqtt = None

from ..common.constants import (
    DNSE_MARKET_DATA_WSS_HOST,
    DNSE_MARKET_DATA_WSS_PATH,
    DNSE_MARKET_DATA_WSS_PORT,
    MQTT_TOPIC_STOCK_INFO,
    MQTT_TOPIC_TOP_PRICE,
)
from ..common.types import DNSEMarketDataTick, DNSEOrderBookEntry



_log = logging.getLogger(__name__)


class DNSEWebSocketClient:
    """
    WebSocket client for DNSE real-time market data.
    
    Uses MQTT over WebSocket protocol to subscribe to price feeds.
    
    Parameters
    ----------
    investor_id : str
        Investor ID (from account info) for authentication.
    jwt_token : str
        JWT token for authentication.
    on_tick : Callable[[DNSEMarketDataTick], None], optional
        Callback for receiving price ticks.
    on_connected : Callable[[], None], optional
        Callback when connected.
    on_disconnected : Callable[[], None], optional
        Callback when disconnected.
    """
    
    def __init__(
        self,
        investor_id: str,
        jwt_token: str,
        on_tick: Optional[Callable[[DNSEMarketDataTick], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
    ):
        if not HAS_MQTT:
            raise ImportError(
                "paho-mqtt is required for WebSocket market data. "
                "Install with: pip install paho-mqtt"
            )
        
        self._investor_id = investor_id
        self._jwt_token = jwt_token
        self._on_tick = on_tick
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        
        self._client: Optional[mqtt.Client] = None
        self._subscribed_symbols: set[str] = set()
        self._is_connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to market data stream."""
        return self._is_connected
    
    @property
    def subscribed_symbols(self) -> set[str]:
        """Get set of subscribed symbols."""
        return self._subscribed_symbols.copy()
    
    def _generate_client_id(self) -> str:
        """Generate unique client ID for MQTT connection."""
        random_suffix = uuid.uuid4().hex[:8]
        return f"dnse-price-json-mqtt-ws-sub-{self._investor_id}-{random_suffix}"
    
    def connect(self) -> None:
        """Connect to the market data WebSocket."""
        if self._client is not None:
            _log.warning("Already connected, disconnecting first...")
            self.disconnect()
        
        self._loop = asyncio.get_event_loop()
        
        # Create MQTT client with WebSocket transport
        client_id = self._generate_client_id()
        self._client = mqtt.Client(
            client_id=client_id,
            transport="websockets",
            protocol=mqtt.MQTTv311,
        )
        self._client.enable_logger(_log)
        
        # Set authentication
        self._client.username_pw_set(
            username=self._investor_id,
            password=self._jwt_token,
        )
        
        # Configure TLS for secure WebSocket
        ssl_context = ssl.create_default_context()
        self._client.tls_set_context(ssl_context)
        
        # Set WebSocket path
        self._client.ws_set_options(path=DNSE_MARKET_DATA_WSS_PATH)
        
        # Set callbacks
        self._client.on_connect = self._on_mqtt_connect
        self._client.on_disconnect = self._on_mqtt_disconnect
        self._client.on_message = self._on_mqtt_message
        
        _log.info(f"Connecting to {DNSE_MARKET_DATA_WSS_HOST}:{DNSE_MARKET_DATA_WSS_PORT}")
        
        # Connect (non-blocking)
        self._client.connect_async(
            host=DNSE_MARKET_DATA_WSS_HOST,
            port=DNSE_MARKET_DATA_WSS_PORT,
        )
        
        # Start network loop in background thread
        self._client.loop_start()
    
    def disconnect(self) -> None:
        """Disconnect from the market data WebSocket."""
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        
        self._is_connected = False
        self._subscribed_symbols.clear()
        
        _log.info("Disconnected from market data WebSocket")
    
    def subscribe(self, symbol: str) -> None:
        """
        Subscribe to both Stock Info (Trades) and Top Price (Bid/Ask).
        """
        self.subscribe_stock_info(symbol)
        self.subscribe_top_price(symbol)

    def subscribe_stock_info(self, symbol: str) -> None:
        if not self._is_connected or self._client is None:
            _log.warning(f"Not connected, queuing StockInfo for {symbol}")
            self._subscribed_symbols.add(f"INFO:{symbol}")
            return
        
        topic = MQTT_TOPIC_STOCK_INFO.format(symbol=symbol)
        self._client.subscribe(topic, qos=0)
        self._subscribed_symbols.add(f"INFO:{symbol}")
        _log.info(f"Subscribed to StockInfo: {topic}")

    def subscribe_top_price(self, symbol: str) -> None:
        if not self._is_connected or self._client is None:
            _log.warning(f"Not connected, queuing TopPrice for {symbol}")
            self._subscribed_symbols.add(f"TOP:{symbol}")
            return
        
        topic = MQTT_TOPIC_TOP_PRICE.format(symbol=symbol)
        self._client.subscribe(topic, qos=0)
        self._subscribed_symbols.add(f"TOP:{symbol}")
        _log.info(f"Subscribed to TopPrice: {topic}")

    def unsubscribe(self, symbol: str) -> None:
        if self._is_connected and self._client is not None:
             # Try unsubscribing from both
             self._client.unsubscribe(MQTT_TOPIC_STOCK_INFO.format(symbol=symbol))
             self._client.unsubscribe(MQTT_TOPIC_TOP_PRICE.format(symbol=symbol))
        
        self._subscribed_symbols.discard(f"INFO:{symbol}")
        self._subscribed_symbols.discard(f"TOP:{symbol}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            _log.info("Connected to DNSE market data WebSocket")
            self._is_connected = True
            
            # Resubscribe to queued symbols
            for item in self._subscribed_symbols:
                # Handle both legacy format and new format if any
                if ":" in item:
                    type_, symbol = item.split(":", 1)
                else:
                    type_ = "INFO"
                    symbol = item
                
                if type_ == "INFO":
                    topic = MQTT_TOPIC_STOCK_INFO.format(symbol=symbol)
                elif type_ == "TOP":
                    topic = MQTT_TOPIC_TOP_PRICE.format(symbol=symbol)
                else:
                    topic = MQTT_TOPIC_STOCK_INFO.format(symbol=symbol)
                
                client.subscribe(topic, qos=0)
                _log.info(f"Resubscribed to {topic}")
            
            # Call connected callback
            if self._on_connected is not None:
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._on_connected)
                else:
                    self._on_connected()
        else:
            _log.error(f"MQTT connection failed with code: {rc}")
            self._is_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        _log.warning(f"Disconnected from DNSE market data (rc={rc})")
        self._is_connected = False
        
        if self._on_disconnected is not None:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._on_disconnected)
            else:
                self._on_disconnected()
    
    def _on_mqtt_message(self, client, userdata, message):
        """Handle incoming MQTT message."""
        try:
            topic = message.topic
            payload = message.payload.decode("utf-8")
            data = json.loads(payload)
            
            tick = None
            
            # Identify message type based on topic
            if "stockinfo" in topic:
                if "/symbol/" in topic:
                    symbol = topic.split("/symbol/")[-1]
                else:
                    symbol = data.get("symbol", "")
                tick = self._parse_stock_info(symbol, data)
                
            elif "topprice" in topic:
                _log.info(f"TopPrice Payload: {payload}")
                if "/symbol/" in topic:
                    symbol = topic.split("/symbol/")[-1]
                else:
                    symbol = data.get("symbol", "")
                tick = self._parse_top_price(symbol, data)
            
            if tick is not None and self._on_tick is not None:
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._on_tick, tick)
                else:
                    self._on_tick(tick)
                    
        except Exception as e:
            _log.error(f"Error processing message: {e}")
    
    def _parse_stock_info(self, symbol: str, data: dict) -> Optional[DNSEMarketDataTick]:
        return DNSEMarketDataTick(
            symbol=symbol,
            timestamp=datetime.now(),
            last_price=Decimal(str(data.get("matchPrice") or data.get("lastPrice") or 0)),
            last_volume=int(data.get("matchQuantity") or data.get("lastVolume") or 0),
            total_volume=int(data.get("totalVolumeTraded") or 0),
            total_value=Decimal(str(data.get("grossTradeAmount") or 0)),
            bid_price=Decimal("0"), bid_volume=0, ask_price=Decimal("0"), ask_volume=0,
            open_price=Decimal(str(data.get("openPrice", 0))),
            high_price=Decimal(str(data.get("highestPrice") or data.get("highPrice") or 0)),
            low_price=Decimal(str(data.get("lowestPrice") or data.get("lowPrice") or 0)),
            close_price=Decimal(str(data.get("referencePrice") or data.get("closePrice") or 0)),
        )

    def _parse_top_price(self, symbol: str, data: dict) -> Optional[DNSEMarketDataTick]:
        # TopPrice has Bid/Ask info
        
        # Parse Bids
        bids = []
        raw_bids = data.get("bid") or []
        for b in raw_bids:
            try:
                price = Decimal(str(b.get("price", 0)))
                qty = int(b.get("qtty") or b.get("quantity") or 0)
                if price > 0 and qty > 0:
                    bids.append(DNSEOrderBookEntry(price=price, quantity=qty))
            except: 
                pass
                
        # Parse Asks (payload uses "offer" usually)
        asks = []
        raw_asks = data.get("offer") or data.get("ask") or []
        for a in raw_asks:
            try:
                price = Decimal(str(a.get("price", 0)))
                qty = int(a.get("qtty") or a.get("quantity") or 0)
                if price > 0 and qty > 0:
                    asks.append(DNSEOrderBookEntry(price=price, quantity=qty))
            except:
                pass
        
        # Best Bid/Ask for backward compatibility
        best_bid = bids[0] if bids else DNSEOrderBookEntry(Decimal(0), 0)
        best_ask = asks[0] if asks else DNSEOrderBookEntry(Decimal(0), 0)

        return DNSEMarketDataTick(
            symbol=symbol,
            timestamp=datetime.now(),
            last_price=Decimal("0"), last_volume=0, total_volume=0, total_value=Decimal("0"),
            open_price=Decimal("0"), high_price=Decimal("0"), low_price=Decimal("0"), close_price=Decimal("0"),
            
            bid_price=best_bid.price,
            bid_volume=best_bid.quantity,
            ask_price=best_ask.price,
            ask_volume=best_ask.quantity,
            
            bids=bids,
            asks=asks
        )

    
    def update_token(self, jwt_token: str) -> None:
        """
        Update JWT token for reconnection.
        """
        self._jwt_token = jwt_token
        
        # If connected, need to reconnect with new token
        if self._is_connected:
            _log.info("Token updated, reconnecting...")
            self.disconnect()
            self.connect()
