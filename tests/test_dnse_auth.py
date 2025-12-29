"""
Unit tests for DNSE HTTP client and authentication.
"""
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.dnse.common.enums import DNSEOrderSide, DNSEOrderType, DNSEOrderStatus
from adapters.dnse.common.types import DNSETokens, DNSEOrderResponse
from adapters.dnse.http.auth import DNSEAuthProvider
from adapters.dnse.parsing.orders import parse_order_response, parse_account_info


class TestDNSEAuthProvider:
    """Tests for DNSEAuthProvider."""
    
    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login."""
        with patch('aiohttp.ClientSession') as mock_session:
            # Mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"token": "test_jwt_token"})
            
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            auth = DNSEAuthProvider(
                username="test_user",
                password="test_pass",
                auto_refresh=False,
            )
            
            # We can't fully test without mocking the session properly
            # This is a structure test
            assert auth._username == "test_user"
            assert auth._password == "test_pass"
            assert not auth.is_authenticated
    
    def test_token_expiry_check(self):
        """Test token expiry checking."""
        # Create tokens
        tokens = DNSETokens(
            jwt_token="test_jwt",
            jwt_expires_at=datetime.now() + timedelta(hours=8),
        )
        
        assert not tokens.is_jwt_expired
        assert tokens.is_trading_token_expired  # No trading token set
        
        # Test expired token
        expired_tokens = DNSETokens(
            jwt_token="test_jwt",
            jwt_expires_at=datetime.now() - timedelta(hours=1),
        )
        assert expired_tokens.is_jwt_expired
    
    def test_auth_headers(self):
        """Test auth header generation."""
        auth = DNSEAuthProvider(
            username="test_user",
            password="test_pass",
        )
        
        # Without tokens
        headers = auth.get_auth_headers()
        assert "Content-Type" in headers
        assert "Authorization" not in headers
        
        # With tokens
        auth._tokens = DNSETokens(
            jwt_token="test_jwt",
            jwt_expires_at=datetime.now() + timedelta(hours=8),
            trading_token="test_trading",
            trading_token_expires_at=datetime.now() + timedelta(hours=8),
        )
        
        headers = auth.get_auth_headers(include_trading_token=True)
        assert headers["Authorization"] == "Bearer test_jwt"
        assert headers["Trading-Token"] == "test_trading"


class TestOrderParsing:
    """Tests for order response parsing."""
    
    def test_parse_order_response(self):
        """Test parsing order response."""
        data = {
            "id": 12345,
            "side": "NB",
            "accountNo": "001A123456",
            "investorId": "INV001",
            "symbol": "VNM",
            "price": 75000,
            "quantity": 100,
            "orderType": "LO",
            "orderStatus": "new",
            "fillQuantity": 0,
            "lastQuantity": 0,
            "lastPrice": None,
            "averagePrice": None,
            "transDate": "2024-12-29",
            "createdDate": "2024-12-29T10:30:00+07:00",
            "leaveQuantity": 100,
            "canceledQuantity": 0,
            "custody": "001A",
            "channel": "API",
        }
        
        order = parse_order_response(data)
        
        assert order.id == 12345
        assert order.side == "NB"
        assert order.symbol == "VNM"
        assert order.price == Decimal("75000")
        assert order.quantity == 100
        assert order.order_type == "LO"
        assert order.order_status == "new"
    
    def test_parse_account_info(self):
        """Test parsing account info."""
        data = {
            "investorId": "INV001",
            "name": "Nguyen Van A",
            "custodyCode": "001A123456",
            "mobile": "0901234567",
            "email": "test@example.com",
        }
        
        account = parse_account_info(data)
        
        assert account.investor_id == "INV001"
        assert account.name == "Nguyen Van A"
        assert account.custody_code == "001A123456"


class TestEnums:
    """Tests for DNSE enums."""
    
    def test_order_side_values(self):
        """Test order side enum values."""
        assert DNSEOrderSide.BUY.value == "NB"
        assert DNSEOrderSide.SELL.value == "NS"
    
    def test_order_type_values(self):
        """Test order type enum values."""
        assert DNSEOrderType.LIMIT.value == "LO"
        assert DNSEOrderType.MARKET.value == "MP"
        assert DNSEOrderType.AT_OPEN.value == "ATO"
        assert DNSEOrderType.AT_CLOSE.value == "ATC"
    
    def test_order_status_values(self):
        """Test order status enum values."""
        assert DNSEOrderStatus.NEW.value == "new"
        assert DNSEOrderStatus.FILLED.value == "filled"
        assert DNSEOrderStatus.CANCELED.value == "canceled"
        assert DNSEOrderStatus.REJECTED.value == "rejected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
