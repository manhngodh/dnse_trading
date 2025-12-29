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

from adapters.dnse.common.constants import (
    DNSE_MARKET_DATA_WSS_HOST,
    DNSE_MARKET_DATA_WSS_PATH,
    DNSE_MARKET_DATA_WSS_PORT,
)
from adapters.dnse.common.types import DNSEMarketDataTick


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
        Subscribe to price updates for a symbol.
        
        Parameters
        ----------
        symbol : str
            Symbol to subscribe to (e.g., "VNM", "VN30F2412").
        """
        if not self._is_connected or self._client is None:
            _log.warning(f"Not connected, queuing subscription for {symbol}")
            self._subscribed_symbols.add(symbol)
            return
        
        topic = f"stock/{symbol}"
        self._client.subscribe(topic, qos=0)
        self._subscribed_symbols.add(symbol)
        
        _log.info(f"Subscribed to {topic}")
    
    def unsubscribe(self, symbol: str) -> None:
        """
        Unsubscribe from price updates for a symbol.
        
        Parameters
        ----------
        symbol : str
            Symbol to unsubscribe from.
        """
        if symbol not in self._subscribed_symbols:
            return
        
        if self._is_connected and self._client is not None:
            topic = f"stock/{symbol}"
            self._client.unsubscribe(topic)
            _log.info(f"Unsubscribed from {topic}")
        
        self._subscribed_symbols.discard(symbol)
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            _log.info("Connected to DNSE market data WebSocket")
            self._is_connected = True
            
            # Resubscribe to queued symbols
            for symbol in self._subscribed_symbols:
                topic = f"stock/{symbol}"
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
            
            # Extract symbol from topic (format: stock/{symbol})
            if topic.startswith("stock/"):
                symbol = topic[6:]
            else:
                symbol = data.get("symbol", "")
            
            # Parse market data tick
            tick = self._parse_tick(symbol, data)
            
            if tick is not None and self._on_tick is not None:
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._on_tick, tick)
                else:
                    self._on_tick(tick)
                    
        except Exception as e:
            _log.error(f"Error processing message: {e}")
    
    def _parse_tick(self, symbol: str, data: dict) -> Optional[DNSEMarketDataTick]:
        """Parse raw MQTT message into DNSEMarketDataTick."""
        try:
            # Parse timestamp
            timestamp_str = data.get("time") or data.get("timestamp")
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                timestamp = datetime.now()
            
            # Create tick
            return DNSEMarketDataTick(
                symbol=symbol,
                timestamp=timestamp,
                last_price=Decimal(str(data.get("lastPrice", 0))),
                last_volume=int(data.get("lastVolume", 0)),
                bid_price=Decimal(str(data.get("bidPrice", 0))),
                bid_volume=int(data.get("bidVolume", 0)),
                ask_price=Decimal(str(data.get("askPrice", 0))),
                ask_volume=int(data.get("askVolume", 0)),
                open_price=Decimal(str(data.get("openPrice", 0))),
                high_price=Decimal(str(data.get("highPrice", 0))),
                low_price=Decimal(str(data.get("lowPrice", 0))),
                close_price=Decimal(str(data.get("closePrice", 0))) if data.get("closePrice") else None,
                total_volume=int(data.get("totalVolume", 0)),
                total_value=Decimal(str(data.get("totalValue", 0))),
            )
        except Exception as e:
            _log.error(f"Failed to parse tick for {symbol}: {e}")
            return None
    
    def update_token(self, jwt_token: str) -> None:
        """
        Update JWT token for reconnection.
        
        Parameters
        ----------
        jwt_token : str
            New JWT token.
        """
        self._jwt_token = jwt_token
        
        # If connected, need to reconnect with new token
        if self._is_connected:
            _log.info("Token updated, reconnecting...")
            symbols = self._subscribed_symbols.copy()
            self.disconnect()
            self.connect()
            for symbol in symbols:
                self.subscribe(symbol)
