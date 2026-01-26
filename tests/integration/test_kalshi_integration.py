"""Integration tests for Kalshi API client.

These tests make real API calls to Kalshi demo environment.
Requires KALSHI_API_KEY and KALSHI_API_SECRET environment variables.
"""

import os

import pytest

from src.shared.api.kalshi import KalshiClient
from src.shared.api.response_models import Balance, Market, Orderbook


@pytest.mark.integration
@pytest.mark.slow
class TestKalshiIntegration:
    """Integration tests for Kalshi API client with real API calls."""

    @pytest.fixture
    def kalshi_client(self) -> KalshiClient:
        """Create Kalshi client for testing.
        
        Requires KALSHI_API_KEY and KALSHI_API_SECRET environment variables.
        """
        api_key = os.getenv("KALSHI_API_KEY")
        api_secret = os.getenv("KALSHI_API_SECRET")
        
        if not api_key or not api_secret:
            pytest.skip("Kalshi API credentials not configured")
        
        return KalshiClient(
            api_key=api_key,
            api_secret=api_secret,
            base_url="https://demo-api.kalshi.co/trade-api/v2",
        )

    def test_authentication(self, kalshi_client: KalshiClient) -> None:
        """Test authentication with Kalshi API."""
        kalshi_client._authenticate()
        
        assert kalshi_client._access_token is not None
        assert kalshi_client._token_expiry > 0

    def test_get_markets(self, kalshi_client: KalshiClient) -> None:
        """Test fetching markets from Kalshi."""
        markets = kalshi_client.get_markets(status="open", limit=10)
        
        assert isinstance(markets, list)
        # May be empty if no markets open
        if len(markets) > 0:
            assert "ticker" in markets[0]
            assert "status" in markets[0]

    def test_get_markets_with_series_filter(self, kalshi_client: KalshiClient) -> None:
        """Test fetching markets filtered by series ticker."""
        # Try to find weather markets
        markets = kalshi_client.get_markets(series_ticker="HIGHNYC", limit=10)
        
        assert isinstance(markets, list)
        # Results depend on what markets are available

    def test_get_market_detail(self, kalshi_client: KalshiClient) -> None:
        """Test fetching single market details."""
        # First get a market ticker
        markets = kalshi_client.get_markets(status="open", limit=1)
        
        if len(markets) == 0:
            pytest.skip("No open markets available")
        
        ticker = markets[0]["ticker"]
        market = kalshi_client.get_market(ticker)
        
        assert market["ticker"] == ticker
        assert "title" in market
        assert "status" in market

    def test_get_orderbook(self, kalshi_client: KalshiClient) -> None:
        """Test fetching orderbook for a market."""
        # Get an open market
        markets = kalshi_client.get_markets(status="open", limit=1)
        
        if len(markets) == 0:
            pytest.skip("No open markets available")
        
        ticker = markets[0]["ticker"]
        orderbook = kalshi_client.get_orderbook(ticker)
        
        assert "yes" in orderbook or "no" in orderbook

    def test_get_balance(self, kalshi_client: KalshiClient) -> None:
        """Test fetching account balance."""
        balance = kalshi_client.get_balance()
        
        assert "balance" in balance
        assert isinstance(balance["balance"], int)

    def test_get_positions(self, kalshi_client: KalshiClient) -> None:
        """Test fetching current positions."""
        positions = kalshi_client.get_positions()
        
        assert isinstance(positions, list)
        # May be empty if no positions

    def test_get_orders(self, kalshi_client: KalshiClient) -> None:
        """Test fetching orders."""
        orders = kalshi_client.get_orders(limit=10)
        
        assert isinstance(orders, list)
        # May be empty if no orders

    def test_get_fills(self, kalshi_client: KalshiClient) -> None:
        """Test fetching fill history."""
        fills = kalshi_client.get_fills(limit=10)
        
        assert isinstance(fills, list)
        # May be empty if no fills

    def test_parse_market_with_pydantic(self, kalshi_client: KalshiClient) -> None:
        """Test parsing Kalshi market response with Pydantic models."""
        markets = kalshi_client.get_markets(status="open", limit=1)
        
        if len(markets) == 0:
            pytest.skip("No open markets available")
        
        # Parse with Pydantic model
        market = Market(**markets[0])
        
        assert isinstance(market, Market)
        assert market.ticker is not None
        assert market.status == "open"

    def test_parse_orderbook_with_pydantic(self, kalshi_client: KalshiClient) -> None:
        """Test parsing Kalshi orderbook response with Pydantic models."""
        markets = kalshi_client.get_markets(status="open", limit=1)
        
        if len(markets) == 0:
            pytest.skip("No open markets available")
        
        ticker = markets[0]["ticker"]
        orderbook_data = kalshi_client.get_orderbook(ticker)
        
        # Parse with Pydantic model
        orderbook = Orderbook(**orderbook_data)
        
        assert isinstance(orderbook, Orderbook)

    def test_parse_balance_with_pydantic(self, kalshi_client: KalshiClient) -> None:
        """Test parsing Kalshi balance response with Pydantic models."""
        balance_data = kalshi_client.get_balance()
        
        # Parse with Pydantic model
        balance = Balance(**balance_data)
        
        assert isinstance(balance, Balance)
        assert balance.balance >= 0

    def test_rate_limiting_enforced(self, kalshi_client: KalshiClient) -> None:
        """Test that rate limiting is enforced across multiple requests."""
        import time
        
        # Make 11 rapid requests (limit is 10/sec)
        start = time.time()
        for _ in range(11):
            kalshi_client.get_balance()
        elapsed = time.time() - start
        
        # Should take at least 1 second due to rate limiting
        assert elapsed >= 1.0

    def test_reauthentication_on_token_expiry(self, kalshi_client: KalshiClient) -> None:
        """Test automatic re-authentication when token expires."""
        # Force token expiry
        kalshi_client._token_expiry = 0.0
        kalshi_client._access_token = None
        
        # This should trigger authentication
        balance = kalshi_client.get_balance()
        
        assert kalshi_client._access_token is not None
        assert "balance" in balance
