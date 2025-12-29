"""
Factory classes for creating DNSE data and execution clients.
"""
import asyncio
from typing import Any, Optional

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import Clock, MessageBus
from nautilus_trader.live.factories import LiveDataClientFactory, LiveExecClientFactory

from adapters.dnse.config import DNSEDataClientConfig, DNSEExecClientConfig
from adapters.dnse.data.client import DNSEDataClient
from adapters.dnse.execution.client import DNSEExecClient
from adapters.dnse.http.client import DNSEHttpClient


class DNSELiveDataClientFactory(LiveDataClientFactory):
    """
    Factory for creating DNSE live data clients.
    """
    
    @staticmethod
    def create(
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: dict[str, Any],
        msgbus: MessageBus,
        cache: Cache,
        clock: Clock,
    ) -> DNSEDataClient:
        """
        Create a new DNSE data client.
        
        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            The event loop.
        name : str
            The client name.
        config : dict[str, Any]
            The configuration dictionary.
        msgbus : MessageBus
            The message bus.
        cache : Cache
            The cache.
        clock : Clock
            The clock.
        
        Returns
        -------
        DNSEDataClient
        """
        # Parse config
        client_config = DNSEDataClientConfig(**config) if isinstance(config, dict) else config
        
        # Create HTTP client
        http_client = DNSEHttpClient(
            username=client_config.username,
            password=client_config.password,
            account_no=client_config.account_no or "",
        )
        
        # Create data client
        return DNSEDataClient(
            loop=loop,
            client=http_client,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            config=client_config,
        )


class DNSELiveExecClientFactory(LiveExecClientFactory):
    """
    Factory for creating DNSE live execution clients.
    """
    
    @staticmethod
    def create(
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: dict[str, Any],
        msgbus: MessageBus,
        cache: Cache,
        clock: Clock,
    ) -> DNSEExecClient:
        """
        Create a new DNSE execution client.
        
        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            The event loop.
        name : str
            The client name.
        config : dict[str, Any]
            The configuration dictionary.
        msgbus : MessageBus
            The message bus.
        cache : Cache
            The cache.
        clock : Clock
            The clock.
        
        Returns
        -------
        DNSEExecClient
        """
        # Parse config
        client_config = DNSEExecClientConfig(**config) if isinstance(config, dict) else config
        
        # Create HTTP client
        http_client = DNSEHttpClient(
            username=client_config.username,
            password=client_config.password,
            account_no=client_config.account_no,
            otp_callback=client_config.otp_callback,
        )
        
        # Create execution client
        return DNSEExecClient(
            loop=loop,
            client=http_client,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            config=client_config,
        )
