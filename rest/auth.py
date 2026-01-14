"""
DNSE authentication provider for managing JWT and trading tokens.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

import aiohttp

from ..common.constants import (
    CONTENT_TYPE_JSON,
    DNSE_API_BASE_URL,
    HEADER_AUTHORIZATION,
    HEADER_CONTENT_TYPE,
    HEADER_SMART_OTP,
    HTTP_TIMEOUT,
    TOKEN_EXPIRY_SECONDS,
    TOKEN_REFRESH_BUFFER_SECONDS,
)
from ..common.types import DNSETokens
from .endpoints import get_login_url, get_trading_token_url


_log = logging.getLogger(__name__)


class DNSEAuthProvider:
    """
    Manages DNSE authentication tokens.
    
    Handles:
    - Layer 1: Login with username/password -> JWT token
    - Layer 2: OTP verification -> Trading token
    - Automatic token refresh
    
    Parameters
    ----------
    username : str
        Login username (email, phone, or custody code).
    password : str
        Login password.
    otp_callback : Callable[[], str], optional
        Callback function to get OTP for trading token.
    base_url : str, optional
        API base URL. Defaults to production.
    auto_refresh : bool, optional
        Whether to automatically refresh tokens. Defaults to True.
    """
    
    def __init__(
        self,
        username: str,
        password: str,
        otp_callback: Optional[Callable[[], str]] = None,
        base_url: str = DNSE_API_BASE_URL,
        auto_refresh: bool = True,
    ):
        self._username = username
        self._password = password
        self._otp_callback = otp_callback
        self._base_url = base_url
        self._auto_refresh = auto_refresh
        
        self._tokens: Optional[DNSETokens] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._is_authenticated = False
        
    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with valid JWT token."""
        if self._tokens is None:
            return False
        return not self._tokens.is_jwt_expired
    
    @property
    def has_trading_token(self) -> bool:
        """Check if has valid trading token for order operations."""
        if self._tokens is None:
            return False
        return not self._tokens.is_trading_token_expired
    
    @property
    def jwt_token(self) -> Optional[str]:
        """Get current JWT token."""
        if self._tokens is None:
            return None
        return self._tokens.jwt_token
    
    @property
    def trading_token(self) -> Optional[str]:
        """Get current trading token."""
        if self._tokens is None:
            return None
        return self._tokens.trading_token
    
    async def connect(self) -> None:
        """Initialize the authentication provider and perform login."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            self._session = aiohttp.ClientSession(timeout=timeout)
        
        # Perform initial login
        await self._login()
        
        # Start refresh task if enabled
        if self._auto_refresh:
            self._start_refresh_task()
    
    async def disconnect(self) -> None:
        """Cleanup and disconnect the authentication provider."""
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
        
        if self._session is not None:
            await self._session.close()
            self._session = None
        
        self._tokens = None
        self._is_authenticated = False
    
    async def _login(self) -> str:
        """
        Perform Layer 1 login to get JWT token.
        
        Returns
        -------
        str
            JWT token.
        
        Raises
        ------
        RuntimeError
            If login fails.
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Call connect() first.")
        
        url = get_login_url(self._base_url)
        payload = {
            "username": self._username,
            "password": self._password,
        }
        headers = {
            HEADER_CONTENT_TYPE: CONTENT_TYPE_JSON,
        }
        
        _log.info(f"Attempting login for user: {self._username}")
        
        async with self._session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Login failed with status {response.status}: {error_text}")
            
            data = await response.json()
            jwt_token = data.get("token")
            
            if not jwt_token:
                raise RuntimeError("Login response missing 'token' field")
            
            # Calculate expiry time (8 hours from now)
            expires_at = datetime.now() + timedelta(seconds=TOKEN_EXPIRY_SECONDS)
            
            self._tokens = DNSETokens(
                jwt_token=jwt_token,
                jwt_expires_at=expires_at,
            )
            self._is_authenticated = True
            
            _log.info(f"Login successful. JWT expires at: {expires_at}")
            return jwt_token
    
    async def get_trading_token(self, otp: Optional[str] = None) -> str:
        """
        Perform Layer 2 OTP verification to get trading token.
        
        Parameters
        ----------
        otp : str, optional
            OTP code. If not provided, will use otp_callback.
        
        Returns
        -------
        str
            Trading token.
        
        Raises
        ------
        RuntimeError
            If OTP verification fails or no OTP provided.
        """
        if self._session is None or not self.is_authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")
        
        # Get OTP from parameter or callback
        if otp is None:
            if self._otp_callback is None:
                raise RuntimeError("No OTP provided and no otp_callback configured")
            otp = self._otp_callback()
        
        url = get_trading_token_url(self._base_url)
        headers = {
            HEADER_AUTHORIZATION: f"Bearer {self.jwt_token}",
            HEADER_SMART_OTP: otp,
            HEADER_CONTENT_TYPE: CONTENT_TYPE_JSON,
        }
        
        _log.info("Requesting trading token with OTP verification...")
        
        async with self._session.post(url, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"OTP verification failed with status {response.status}: {error_text}")
            
            data = await response.json()
            trading_token = data.get("tradingToken")
            
            if not trading_token:
                raise RuntimeError("OTP response missing 'tradingToken' field")
            
            # Calculate expiry time (8 hours from now)
            expires_at = datetime.now() + timedelta(seconds=TOKEN_EXPIRY_SECONDS)
            
            # Update tokens with trading token
            self._tokens = DNSETokens(
                jwt_token=self._tokens.jwt_token,
                jwt_expires_at=self._tokens.jwt_expires_at,
                trading_token=trading_token,
                trading_token_expires_at=expires_at,
            )
            
            _log.info(f"Trading token obtained. Expires at: {expires_at}")
            return trading_token
    
    async def ensure_authenticated(self) -> None:
        """Ensure we have a valid JWT token, refreshing if needed."""
        if not self.is_authenticated:
            await self._login()
    
    async def ensure_trading_token(self) -> None:
        """Ensure we have a valid trading token, requesting OTP if needed."""
        await self.ensure_authenticated()
        
        if not self.has_trading_token:
            await self.get_trading_token()
    
    def _start_refresh_task(self) -> None:
        """Start background task to refresh tokens before expiry."""
        if self._refresh_task is not None:
            return
        
        async def refresh_loop():
            while True:
                try:
                    # Check if JWT needs refresh
                    if self._tokens is not None:
                        time_to_jwt_expiry = (
                            self._tokens.jwt_expires_at - datetime.now()
                        ).total_seconds()
                        
                        if time_to_jwt_expiry < TOKEN_REFRESH_BUFFER_SECONDS:
                            _log.info("Refreshing JWT token...")
                            await self._login()
                    
                    # Sleep for a while before checking again
                    await asyncio.sleep(60)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    _log.error(f"Error in token refresh loop: {e}")
                    await asyncio.sleep(30)
        
        self._refresh_task = asyncio.create_task(refresh_loop())
    
    def get_auth_headers(self, include_trading_token: bool = False) -> dict:
        """
        Get authentication headers for API requests.
        
        Parameters
        ----------
        include_trading_token : bool
            Whether to include trading token (for order operations).
        
        Returns
        -------
        dict
            Headers dictionary.
        """
        headers = {
            HEADER_CONTENT_TYPE: CONTENT_TYPE_JSON,
        }
        
        if self.jwt_token:
            headers[HEADER_AUTHORIZATION] = f"Bearer {self.jwt_token}"
        
        if include_trading_token and self.trading_token:
            headers["Trading-Token"] = self.trading_token
        
        return headers
