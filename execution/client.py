"""
DNSE Execution Client for NautilusTrader.

Provides order execution and account management via DNSE REST API.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Optional

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import Clock, MessageBus
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.messages import (
    CancelOrder,
    ModifyOrder,
    SubmitOrder,
)
from nautilus_trader.execution.reports import (
    OrderStatusReport,
    FillReport,
    PositionStatusReport,
)
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.model.enums import (
    AccountType,
    LiquiditySide,
    OmsType,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
from nautilus_trader.model.identifiers import (
    AccountId,
    ClientId,
    ClientOrderId,
    InstrumentId,
    StrategyId,
    TradeId,
    Venue,
    VenueOrderId,
)
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Money, Price, Quantity

from adapters.dnse.common.enums import DNSEOrderSide, DNSEOrderStatus, DNSEOrderType
from adapters.dnse.config import DNSEExecClientConfig
from adapters.dnse.http.client import DNSEHttpClient
from adapters.dnse.parsing.orders import parse_order_response


_log = logging.getLogger(__name__)


class DNSEExecClient(LiveExecutionClient):
    """
    DNSE Execution Client for live trading.
    
    Handles order submission, cancellation, and position management
    via the DNSE REST API.
    
    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        The event loop.
    client : DNSEHttpClient
        The HTTP client.
    msgbus : MessageBus
        The message bus.
    cache : Cache
        The cache.
    clock : Clock
        The clock.
    config : DNSEExecClientConfig
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
        config: DNSEExecClientConfig,
    ):
        super().__init__(
            loop=loop,
            client_id=ClientId("DNSE"),
            venue=self.VENUE,
            oms_type=OmsType.NETTING,
            account_type=AccountType.MARGIN,
            base_currency=None,  # VND
            msgbus=msgbus,
            cache=cache,
            clock=clock,
        )
        
        self._http_client = client
        self._config = config
        self._account_id: Optional[AccountId] = None
        
        # Order ID mappings
        self._order_id_map: dict[ClientOrderId, int] = {}  # client_order_id -> dnse_order_id
        self._dnse_order_map: dict[int, ClientOrderId] = {}  # dnse_order_id -> client_order_id
    
    async def _connect(self) -> None:
        """Connect to DNSE execution services."""
        _log.info("Connecting DNSE execution client...")
        
        # Connect HTTP client
        await self._http_client.connect()
        
        # Get account info and set account ID
        account_info = await self._http_client.get_account_info()
        investor_id = account_info.get("investorId", "")
        
        self._account_id = AccountId(f"DNSE-{investor_id}")
        
        # Request trading token if OTP callback is configured
        if self._config.otp_callback is not None:
            try:
                await self._http_client.request_trading_token()
                _log.info("Trading token obtained")
            except Exception as e:
                _log.warning(f"Failed to get trading token: {e}. OTP required for orders.")
        
        _log.info(f"DNSE execution client connected (account: {self._account_id})")
    
    async def _disconnect(self) -> None:
        """Disconnect from DNSE execution services."""
        _log.info("Disconnecting DNSE execution client...")
        
        await self._http_client.disconnect()
        
        self._order_id_map.clear()
        self._dnse_order_map.clear()
        
        _log.info("DNSE execution client disconnected")
    
    @property
    def account_id(self) -> AccountId:
        """Get the account ID."""
        return self._account_id or AccountId("DNSE-UNKNOWN")
    
    async def _submit_order(self, command: SubmitOrder) -> None:
        """Submit an order to DNSE."""
        order = command.order
        
        _log.info(f"Submitting order: {order}")
        
        try:
            # Convert NautilusTrader order to DNSE format
            symbol = order.instrument_id.symbol.value
            side = self._convert_order_side(order.side)
            order_type = self._convert_order_type(order.order_type)
            price = Decimal(str(order.price)) if hasattr(order, 'price') and order.price else Decimal("0")
            quantity = int(order.quantity)
            
            # Check if we have trading token
            if not self._http_client.can_trade:
                _log.error("No trading token available. OTP verification required.")
                self._generate_order_rejected(
                    order=order,
                    reason="No trading token. OTP verification required.",
                )
                return
            
            # Determine if derivative order
            is_derivative = self._is_derivative_symbol(symbol)
            
            # Place order via API
            if is_derivative:
                response = await self._http_client.place_derivative_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    price=price,
                    quantity=quantity,
                )
            else:
                response = await self._http_client.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    price=price,
                    quantity=quantity,
                )
            
            # Parse response
            order_response = parse_order_response(response)
            
            # Store order ID mapping
            self._order_id_map[order.client_order_id] = order_response.id
            self._dnse_order_map[order_response.id] = order.client_order_id
            
            # Generate order accepted event
            self._generate_order_accepted(
                strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,
                client_order_id=order.client_order_id,
                venue_order_id=VenueOrderId(str(order_response.id)),
            )
            
            _log.info(f"Order accepted: {order.client_order_id} -> {order_response.id}")
            
            # Check if already filled
            if order_response.order_status == DNSEOrderStatus.FILLED.value:
                self._generate_order_filled(
                    strategy_id=order.strategy_id,
                    instrument_id=order.instrument_id,
                    client_order_id=order.client_order_id,
                    venue_order_id=VenueOrderId(str(order_response.id)),
                    fill_qty=Quantity(order_response.fill_quantity, 0),
                    fill_price=Price(order_response.average_price or order_response.price, 2),
                )
            elif order_response.order_status == DNSEOrderStatus.REJECTED.value:
                self._generate_order_rejected(
                    order=order,
                    reason=order_response.error or "Order rejected by exchange",
                )
                
        except Exception as e:
            _log.error(f"Order submission failed: {e}")
            self._generate_order_rejected(
                order=order,
                reason=str(e),
            )
    
    async def _cancel_order(self, command: CancelOrder) -> None:
        """Cancel an order."""
        _log.info(f"Cancelling order: {command.client_order_id}")
        
        try:
            # Get DNSE order ID
            dnse_order_id = self._order_id_map.get(command.client_order_id)
            if dnse_order_id is None:
                _log.error(f"Unknown order: {command.client_order_id}")
                return
            
            # Determine if derivative order
            symbol = command.instrument_id.symbol.value
            is_derivative = self._is_derivative_symbol(symbol)
            
            # Cancel via API
            if is_derivative:
                await self._http_client.cancel_derivative_order(dnse_order_id)
            else:
                await self._http_client.cancel_order(dnse_order_id)
            
            # Generate order canceled event
            self._generate_order_canceled(
                strategy_id=command.strategy_id,
                instrument_id=command.instrument_id,
                client_order_id=command.client_order_id,
                venue_order_id=command.venue_order_id,
            )
            
            _log.info(f"Order cancelled: {command.client_order_id}")
            
        except Exception as e:
            _log.error(f"Order cancellation failed: {e}")
    
    async def _modify_order(self, command: ModifyOrder) -> None:
        """Modify an order (not supported by DNSE)."""
        _log.warning("Order modification not supported by DNSE. Cancel and replace instead.")
    
    def _convert_order_side(self, side: OrderSide) -> DNSEOrderSide:
        """Convert NautilusTrader OrderSide to DNSE."""
        if side == OrderSide.BUY:
            return DNSEOrderSide.BUY
        elif side == OrderSide.SELL:
            return DNSEOrderSide.SELL
        else:
            raise ValueError(f"Unsupported order side: {side}")
    
    def _convert_order_type(self, order_type: OrderType) -> DNSEOrderType:
        """Convert NautilusTrader OrderType to DNSE."""
        if order_type == OrderType.LIMIT:
            return DNSEOrderType.LIMIT
        elif order_type == OrderType.MARKET:
            return DNSEOrderType.MARKET
        else:
            raise ValueError(f"Unsupported order type: {order_type}")
    
    def _is_derivative_symbol(self, symbol: str) -> bool:
        """Check if symbol is a derivative (futures/options)."""
        # VN30F followed by YYMM is a derivative
        return symbol.startswith("VN30F") or symbol.endswith("F")
    
    def _generate_order_accepted(
        self,
        strategy_id: StrategyId,
        instrument_id: InstrumentId,
        client_order_id: ClientOrderId,
        venue_order_id: VenueOrderId,
    ) -> None:
        """Generate order accepted event."""
        from nautilus_trader.execution.messages import OrderAccepted
        
        event = OrderAccepted(
            trader_id=self.trader_id,
            strategy_id=strategy_id,
            instrument_id=instrument_id,
            client_order_id=client_order_id,
            venue_order_id=venue_order_id,
            account_id=self.account_id,
            event_id=UUID4(),
            ts_event=self._clock.timestamp_ns(),
            ts_init=self._clock.timestamp_ns(),
        )
        self._send_event(event)
    
    def _generate_order_rejected(self, order, reason: str) -> None:
        """Generate order rejected event."""
        from nautilus_trader.execution.messages import OrderRejected
        
        event = OrderRejected(
            trader_id=self.trader_id,
            strategy_id=order.strategy_id,
            instrument_id=order.instrument_id,
            client_order_id=order.client_order_id,
            account_id=self.account_id,
            reason=reason,
            event_id=UUID4(),
            ts_event=self._clock.timestamp_ns(),
            ts_init=self._clock.timestamp_ns(),
        )
        self._send_event(event)
    
    def _generate_order_canceled(
        self,
        strategy_id: StrategyId,
        instrument_id: InstrumentId,
        client_order_id: ClientOrderId,
        venue_order_id: VenueOrderId,
    ) -> None:
        """Generate order canceled event."""
        from nautilus_trader.execution.messages import OrderCanceled
        
        event = OrderCanceled(
            trader_id=self.trader_id,
            strategy_id=strategy_id,
            instrument_id=instrument_id,
            client_order_id=client_order_id,
            venue_order_id=venue_order_id,
            account_id=self.account_id,
            event_id=UUID4(),
            ts_event=self._clock.timestamp_ns(),
            ts_init=self._clock.timestamp_ns(),
        )
        self._send_event(event)
    
    def _generate_order_filled(
        self,
        strategy_id: StrategyId,
        instrument_id: InstrumentId,
        client_order_id: ClientOrderId,
        venue_order_id: VenueOrderId,
        fill_qty: Quantity,
        fill_price: Price,
    ) -> None:
        """Generate order filled event."""
        from nautilus_trader.execution.messages import OrderFilled
        from nautilus_trader.model.objects import Money
        
        instrument = self._cache.instrument(instrument_id)
        if instrument is None:
            _log.error(f"No instrument found for {instrument_id}")
            return
        
        event = OrderFilled(
            trader_id=self.trader_id,
            strategy_id=strategy_id,
            instrument_id=instrument_id,
            client_order_id=client_order_id,
            venue_order_id=venue_order_id,
            account_id=self.account_id,
            trade_id=TradeId(str(self._clock.timestamp_ns())),
            order_side=OrderSide.BUY,  # TODO: Track order side
            order_type=OrderType.LIMIT,
            last_qty=fill_qty,
            last_px=fill_price,
            currency=instrument.quote_currency,
            commission=Money(0, instrument.quote_currency),
            liquidity_side=LiquiditySide.TAKER,
            event_id=UUID4(),
            ts_event=self._clock.timestamp_ns(),
            ts_init=self._clock.timestamp_ns(),
        )
        self._send_event(event)
    
    def _send_event(self, event) -> None:
        """Send event to message bus."""
        self._msgbus.send(endpoint="Portfolio", msg=event)
