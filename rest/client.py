"""
Async HTTP client for DNSE REST API.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Any, Optional

import aiohttp

from ..common.constants import (
    DNSE_API_BASE_URL,
    HTTP_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)
from ..common.enums import DNSEOrderSide, DNSEOrderType
from .auth import DNSEAuthProvider
from .endpoints import (
    get_account_info_url,
    get_base_buying_power_url,
    get_base_cancel_order_url,
    get_base_holdings_url,
    get_base_loan_packages_url,
    get_base_order_detail_url,
    get_base_orders_url,
    get_derivative_cancel_order_url,
    get_derivative_orders_url,
    get_derivative_positions_url,
    get_sub_accounts_url,
)


_log = logging.getLogger(__name__)


class DNSEHttpClient:
    """
    Async HTTP client for DNSE REST API.
    
    Handles all REST API calls with:
    - Automatic authentication header injection
    - Request retry with exponential backoff
    - Error handling
    
    Parameters
    ----------
    username : str
        Login username.
    password : str
        Login password.
    account_no : str
        Trading sub-account number.
    otp_callback : Callable[[], str], optional
        Callback to get OTP for trading token.
    base_url : str, optional
        API base URL.
    """
    
    def __init__(
        self,
        username: str,
        password: str,
        account_no: str,
        otp_callback=None,
        base_url: str = DNSE_API_BASE_URL,
    ):
        self._account_no = account_no
        self._base_url = base_url
        
        self._auth_provider = DNSEAuthProvider(
            username=username,
            password=password,
            otp_callback=otp_callback,
            base_url=base_url,
        )
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def account_no(self) -> str:
        """Get configured account number."""
        return self._account_no
    
    @property
    def is_connected(self) -> bool:
        """Check if connected and authenticated."""
        return self._auth_provider.is_authenticated
    
    @property
    def can_trade(self) -> bool:
        """Check if has trading token for order operations."""
        return self._auth_provider.has_trading_token
    
    async def connect(self) -> None:
        """Connect and authenticate."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            self._session = aiohttp.ClientSession(timeout=timeout)
        
        await self._auth_provider.connect()
        _log.info("DNSE HTTP client connected")
    
    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        await self._auth_provider.disconnect()
        
        if self._session is not None:
            await self._session.close()
            self._session = None
        
        _log.info("DNSE HTTP client disconnected")
    
    async def request_trading_token(self, otp: Optional[str] = None) -> str:
        """
        Request trading token with OTP verification.
        
        Parameters
        ----------
        otp : str, optional
            OTP code. Uses callback if not provided.
        
        Returns
        -------
        str
            Trading token.
        """
        return await self._auth_provider.get_trading_token(otp)
    
    async def _request(
        self,
        method: str,
        url: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
        require_trading_token: bool = False,
    ) -> Any:
        """
        Make an HTTP request with retry logic.
        
        Parameters
        ----------
        method : str
            HTTP method (GET, POST, DELETE).
        url : str
            Full URL.
        json_data : dict, optional
            JSON body for POST requests.
        params : dict, optional
            Query parameters.
        require_trading_token : bool
            Whether to include trading token in headers.
        
        Returns
        -------
        Any
            JSON response data.
        """
        if self._session is None:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # Ensure authenticated
        if require_trading_token:
            await self._auth_provider.ensure_trading_token()
        else:
            await self._auth_provider.ensure_authenticated()
        
        headers = self._auth_provider.get_auth_headers(
            include_trading_token=require_trading_token
        )
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                _log.debug(f"Request [{attempt + 1}/{MAX_RETRIES}]: {method} {url}")
                
                async with self._session.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                    headers=headers,
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        if response_text:
                            return await response.json()
                        return {}
                    
                    elif response.status == 401:
                        # Token expired, re-authenticate
                        _log.warning("Token expired, re-authenticating...")
                        await self._auth_provider._login()
                        headers = self._auth_provider.get_auth_headers(
                            include_trading_token=require_trading_token
                        )
                        continue
                    
                    else:
                        last_error = f"HTTP {response.status}: {response_text}"
                        _log.warning(f"Request failed: {last_error}")
                
            except aiohttp.ClientError as e:
                last_error = str(e)
                _log.warning(f"Request error: {e}")
            
            # Wait before retry
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))
        
        raise RuntimeError(f"Request failed after {MAX_RETRIES} retries: {last_error}")
    
    # =========================================================================
    # Account APIs
    # =========================================================================
    
    async def get_account_info(self) -> dict:
        """Get account information."""
        url = get_account_info_url(self._base_url)
        return await self._request("GET", url)
    
    async def get_sub_accounts(self) -> list:
        """Get list of sub-accounts."""
        url = get_sub_accounts_url(self._base_url)
        return await self._request("GET", url)
    
    # =========================================================================
    # Base Trading APIs (Stocks)
    # =========================================================================
    
    async def get_loan_packages(self) -> list:
        """Get available loan packages for margin trading."""
        url = get_base_loan_packages_url(self._base_url)
        return await self._request("GET", url)
    
    async def get_buying_power(self, symbol: str, loan_package_id: int = 0) -> dict:
        """Get buying power for a symbol."""
        url = get_base_buying_power_url(self._base_url)
        params = {
            "accountNo": self._account_no,
            "symbol": symbol,
            "loanPackageId": loan_package_id,
        }
        return await self._request("GET", url, params=params)
    
    async def get_holdings(self) -> list:
        """Get current holdings."""
        url = get_base_holdings_url(self._base_url)
        params = {"accountNo": self._account_no}
        return await self._request("GET", url, params=params)
    
    async def get_orders(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list:
        """
        Get order book (list of orders).
        
        Parameters
        ----------
        from_date : str, optional
            Start date (YYYY-MM-DD).
        to_date : str, optional
            End date (YYYY-MM-DD).
        
        Returns
        -------
        list
            List of orders.
        """
        url = get_base_orders_url(self._base_url)
        params = {"accountNo": self._account_no}
        
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        
        return await self._request("GET", url, params=params)
    
    async def get_order_detail(self, order_id: int) -> dict:
        """Get order detail by ID."""
        url = get_base_order_detail_url(self._base_url, order_id)
        return await self._request("GET", url)
    
    async def place_order(
        self,
        symbol: str,
        side: DNSEOrderSide,
        order_type: DNSEOrderType,
        price: Decimal,
        quantity: int,
        loan_package_id: int = 0,
    ) -> dict:
        """
        Place a base securities order.
        
        Parameters
        ----------
        symbol : str
            Symbol code (e.g., "VNM", "VIC").
        side : DNSEOrderSide
            Buy (NB) or Sell (NS).
        order_type : DNSEOrderType
            Order type (LO, MP, etc.).
        price : Decimal
            Order price (for limit orders).
        quantity : int
            Order quantity.
        loan_package_id : int, optional
            Loan package ID for margin orders.
        
        Returns
        -------
        dict
            Order response.
        """
        url = get_base_orders_url(self._base_url)
        
        payload = {
            "symbol": symbol,
            "side": side.value,
            "orderType": order_type.value,
            "price": float(price),
            "quantity": quantity,
            "loanPackageId": loan_package_id,
            "accountNo": self._account_no,
        }
        
        _log.info(f"Placing order: {side.value} {quantity} {symbol} @ {price}")
        print(f"DEBUG: Order Payload: {payload}")
        
        return await self._request(
            "POST", url, json_data=payload, require_trading_token=True
        )
    
    async def cancel_order(self, order_id: int) -> dict:
        """
        Cancel an order.
        
        Parameters
        ----------
        order_id : int
            Order ID to cancel.
        
        Returns
        -------
        dict
            Cancel response.
        """
        url = get_base_cancel_order_url(self._base_url, order_id, self._account_no)
        
        _log.info(f"Cancelling order: {order_id}")
        
        return await self._request("DELETE", url, require_trading_token=True)
    
    # =========================================================================
    # Derivative Trading APIs
    # =========================================================================
    
    async def get_derivative_positions(self) -> list:
        """Get derivative positions."""
        url = get_derivative_positions_url(self._base_url)
        params = {"accountNo": self._account_no}
        return await self._request("GET", url, params=params)
    
    async def place_derivative_order(
        self,
        symbol: str,
        side: DNSEOrderSide,
        order_type: DNSEOrderType,
        price: Decimal,
        quantity: int,
        loan_package_id: int = 0,
    ) -> dict:
        """
        Place a derivative order.
        
        Parameters
        ----------
        symbol : str
            Derivative symbol (e.g., "VN30F2412").
        side : DNSEOrderSide
            Buy (NB) or Sell (NS).
        order_type : DNSEOrderType
            Order type (LO, ATO, etc.).
        price : Decimal
            Order price.
        quantity : int
            Order quantity.
        loan_package_id : int, optional
            Loan package ID.
        
        Returns
        -------
        dict
            Order response.
        """
        url = get_derivative_orders_url(self._base_url)
        
        payload = {
            "symbol": symbol,
            "side": side.value,
            "orderType": order_type.value,
            "price": float(price),
            "quantity": quantity,
            "loanPackageId": loan_package_id,
            "accountNo": self._account_no,
        }
        
        _log.info(f"Placing derivative order: {side.value} {quantity} {symbol} @ {price}")
        
        return await self._request(
            "POST", url, json_data=payload, require_trading_token=True
        )
    
    async def cancel_derivative_order(self, order_id: int) -> dict:
        """
        Cancel a derivative order.
        
        Parameters
        ----------
        order_id : int
            Order ID to cancel.
        
        Returns
        -------
        dict
            Cancel response.
        """
        url = get_derivative_cancel_order_url(self._base_url, order_id, self._account_no)
        
        _log.info(f"Cancelling derivative order: {order_id}")
        
        return await self._request("DELETE", url, require_trading_token=True)
