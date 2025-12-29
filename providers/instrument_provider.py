"""
DNSE Instrument Provider for KRX symbols.

Provides instrument lookup and loading for Vietnamese securities.
"""
import logging
from decimal import Decimal
from typing import Optional

from nautilus_trader.model.currencies import Currency
from nautilus_trader.model.enums import AssetClass
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import Equity, Future
from nautilus_trader.model.objects import Price, Quantity

from adapters.dnse.common.enums import DNSEExchange
from adapters.dnse.config import DNSEInstrumentProviderConfig
from adapters.dnse.http.client import DNSEHttpClient


_log = logging.getLogger(__name__)


# Vietnamese Dong currency
VND = Currency(
    code="VND",
    precision=0,
    iso4217=704,
    name="Vietnamese Dong",
    currency_type=1,  # FIAT
)


class DNSEInstrumentProvider:
    """
    Instrument provider for DNSE/KRX securities.
    
    Provides instrument definitions for Vietnamese stocks and derivatives.
    
    Parameters
    ----------
    client : DNSEHttpClient
        The HTTP client for API calls.
    config : DNSEInstrumentProviderConfig
        The configuration.
    """
    
    VENUE = Venue("DNSE")
    
    # Common Vietnamese stocks with their lot sizes and tick sizes
    # Format: symbol -> (exchange, lot_size, tick_size, price_precision)
    KNOWN_SYMBOLS = {
        # HOSE blue chips
        "VNM": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "VIC": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "VHM": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "VCB": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "BID": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "FPT": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "MSN": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "MWG": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "HPG": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "TCB": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "VPB": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "MBB": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "ACB": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "STB": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "SSI": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "VND": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "HCM": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "VCI": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "PNJ": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "REE": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "GAS": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "PLX": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "POW": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "PVD": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "VRE": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "NVL": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "BCM": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "DGC": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "DCM": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        "DPM": (DNSEExchange.HOSE, 100, Decimal("10"), 0),
        
        # HNX stocks
        "SHS": (DNSEExchange.HNX, 100, Decimal("100"), 0),
        "PVS": (DNSEExchange.HNX, 100, Decimal("100"), 0),
        "IDC": (DNSEExchange.HNX, 100, Decimal("100"), 0),
    }
    
    def __init__(
        self,
        client: DNSEHttpClient,
        config: DNSEInstrumentProviderConfig,
    ):
        self._client = client
        self._config = config
        self._instruments: dict[InstrumentId, Equity | Future] = {}
        self._loaded = False
    
    @property
    def instruments(self) -> dict[InstrumentId, Equity | Future]:
        """Get all loaded instruments."""
        return self._instruments.copy()
    
    async def load_all(self) -> None:
        """Load all known instruments."""
        _log.info("Loading all DNSE instruments...")
        
        for symbol in self.KNOWN_SYMBOLS:
            await self.load_instrument(symbol)
        
        self._loaded = True
        _log.info(f"Loaded {len(self._instruments)} instruments")
    
    async def load_symbols(self, symbols: list[str]) -> None:
        """Load specific instruments by symbol."""
        _log.info(f"Loading {len(symbols)} DNSE instruments...")
        
        for symbol in symbols:
            await self.load_instrument(symbol)
        
        _log.info(f"Loaded {len(self._instruments)} instruments")
    
    async def load_instrument(self, symbol: str) -> Optional[Equity | Future]:
        """
        Load a single instrument by symbol.
        
        Parameters
        ----------
        symbol : str
            The symbol to load (e.g., "VNM", "VN30F2412").
        
        Returns
        -------
        Equity | Future | None
            The loaded instrument, or None if not found.
        """
        instrument_id = InstrumentId(
            symbol=Symbol(symbol),
            venue=self.VENUE,
        )
        
        # Check if already loaded
        if instrument_id in self._instruments:
            return self._instruments[instrument_id]
        
        # Check if it's a derivative
        if self._is_derivative(symbol):
            instrument = self._create_future_instrument(symbol)
        else:
            instrument = self._create_equity_instrument(symbol)
        
        if instrument is not None:
            self._instruments[instrument_id] = instrument
            _log.debug(f"Loaded instrument: {instrument_id}")
        
        return instrument
    
    def get_instrument(self, instrument_id: InstrumentId) -> Optional[Equity | Future]:
        """Get an instrument by ID."""
        return self._instruments.get(instrument_id)
    
    def _is_derivative(self, symbol: str) -> bool:
        """Check if symbol is a derivative (futures/options)."""
        # VN30F followed by YYMM is a VN30 futures
        return symbol.startswith("VN30F") or "F" in symbol[-5:]
    
    def _create_equity_instrument(self, symbol: str) -> Optional[Equity]:
        """Create an Equity instrument."""
        # Get symbol info from known symbols or use defaults
        if symbol in self.KNOWN_SYMBOLS:
            exchange, lot_size, tick_size, price_precision = self.KNOWN_SYMBOLS[symbol]
        else:
            # Default values for unknown symbols
            exchange = DNSEExchange.HOSE
            lot_size = 100
            tick_size = Decimal("10")
            price_precision = 0
        
        instrument_id = InstrumentId(
            symbol=Symbol(symbol),
            venue=self.VENUE,
        )
        
        try:
            return Equity(
                instrument_id=instrument_id,
                raw_symbol=Symbol(symbol),
                currency=VND,
                price_precision=price_precision,
                price_increment=Price(tick_size, price_precision),
                lot_size=Quantity(lot_size, 0),
                isin=None,
                ts_event=0,
                ts_init=0,
            )
        except Exception as e:
            _log.error(f"Failed to create equity instrument for {symbol}: {e}")
            return None
    
    def _create_future_instrument(self, symbol: str) -> Optional[Future]:
        """Create a Future instrument for VN30 derivatives."""
        instrument_id = InstrumentId(
            symbol=Symbol(symbol),
            venue=self.VENUE,
        )
        
        # Parse expiry from symbol (e.g., VN30F2412 -> Dec 2024)
        expiry_str = self._parse_future_expiry(symbol)
        
        try:
            # VN30 futures specifications
            return Future(
                instrument_id=instrument_id,
                raw_symbol=Symbol(symbol),
                asset_class=AssetClass.INDEX,
                currency=VND,
                price_precision=1,
                price_increment=Price(Decimal("0.1"), 1),
                multiplier=Quantity(100000, 0),  # 100,000 VND per point
                lot_size=Quantity(1, 0),
                underlying=symbol[:4],  # VN30
                activation_ns=0,
                expiration_ns=0,  # Would need to calculate from expiry date
                ts_event=0,
                ts_init=0,
            )
        except Exception as e:
            _log.error(f"Failed to create future instrument for {symbol}: {e}")
            return None
    
    def _parse_future_expiry(self, symbol: str) -> str:
        """Parse expiry from futures symbol (VN30FYYMM format)."""
        # VN30F2412 -> 2412 (Dec 2024)
        if len(symbol) >= 9 and symbol.startswith("VN30F"):
            return symbol[5:9]
        return ""
