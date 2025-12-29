"""
Configuration classes for DNSE data and execution clients.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from nautilus_trader.config import NautilusConfig


@dataclass
class DNSEDataClientConfig(NautilusConfig, frozen=True):
    """
    Configuration for the DNSE data client.
    
    Parameters
    ----------
    username : str
        Login username (email, phone number, or custody code).
    password : str
        Login password.
    account_no : str, optional
        Trading sub-account number. If not provided, will use primary account.
    instrument_provider : InstrumentProviderConfig, optional
        Configuration for the instrument provider.
    """
    username: str = ""
    password: str = ""
    account_no: str = ""
    
    def __post_init__(self):
        if not self.username:
            raise ValueError("username cannot be empty")
        if not self.password:
            raise ValueError("password cannot be empty")


@dataclass
class DNSEExecClientConfig(NautilusConfig, frozen=True):
    """
    Configuration for the DNSE execution client.
    
    Parameters
    ----------
    username : str
        Login username (email, phone number, or custody code).
    password : str
        Login password.
    account_no : str
        Trading sub-account number.
    otp_callback : Callable[[], str], optional
        Callback function to get OTP for trading token.
        If not provided, trading operations will fail.
    auto_refresh_tokens : bool
        Whether to automatically refresh tokens before expiry.
    use_derivative : bool
        Whether to enable derivative trading endpoints.
    """
    username: str = ""
    password: str = ""
    account_no: str = ""
    otp_callback: Optional[Callable[[], str]] = None
    auto_refresh_tokens: bool = True
    use_derivative: bool = False
    
    def __post_init__(self):
        if not self.username:
            raise ValueError("username cannot be empty")
        if not self.password:
            raise ValueError("password cannot be empty")
        if not self.account_no:
            raise ValueError("account_no cannot be empty")


@dataclass
class DNSEInstrumentProviderConfig(NautilusConfig, frozen=True):
    """
    Configuration for the DNSE instrument provider.
    
    Parameters
    ----------
    load_all : bool
        Whether to load all available instruments on startup.
    load_symbols : list[str], optional
        Specific symbols to load (e.g., ["VNM", "VIC", "VN30F2412"]).
    """
    load_all: bool = False
    load_symbols: list = field(default_factory=list)
