"""Smoke test for Kalshi API with RSA key authentication.

Hits the real Kalshi demo sandbox to verify:
- RSA key auth headers work
- Market fetching returns valid data
- Balance endpoint is accessible
- Order/fill/position queries execute without error

Requires KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH environment variables.
Skipped automatically when credentials are not available.
"""

import os

import pytest

from src.shared.api.kalshi import KalshiClient


def _get_client() -> KalshiClient:
    """Create a KalshiClient with RSA auth from environment."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")

    if not api_key_id or not private_key_path:
        pytest.skip("KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY_PATH not set")

    if not os.path.isfile(private_key_path):
        pytest.skip(f"Private key not found: {private_key_path}")

    return KalshiClient(
        api_key_id=api_key_id,
        private_key_path=private_key_path,
        base_url=os.getenv(
            "KALSHI_API_BASE", "https://demo-api.kalshi.co/trade-api/v2"
        ),
    )


@pytest.mark.integration
@pytest.mark.slow
class TestKalshiSmoke:
    """Smoke tests for Kalshi API with RSA authentication."""

    @pytest.fixture
    def client(self) -> KalshiClient:
        """Create authenticated Kalshi client."""
        return _get_client()

    def test_auth_headers_generated(self, client: KalshiClient) -> None:
        """Test RSA auth headers are generated without error."""
        headers = client._get_auth_headers("GET", "/trade-api/v2/markets")
        assert "KALSHI-ACCESS-KEY" in headers
        assert "KALSHI-ACCESS-TIMESTAMP" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers

    def test_get_markets(self, client: KalshiClient) -> None:
        """Test fetching markets from Kalshi sandbox."""
        markets = client.get_markets(limit=5)
        assert isinstance(markets, list)
        # Sandbox may or may not have open markets, but call must succeed

    def test_get_balance(self, client: KalshiClient) -> None:
        """Test fetching account balance."""
        balance = client.get_balance()
        assert isinstance(balance, (int, float, dict))

    def test_get_positions(self, client: KalshiClient) -> None:
        """Test fetching positions (may be empty)."""
        positions = client.get_positions()
        assert isinstance(positions, list)

    def test_get_fills(self, client: KalshiClient) -> None:
        """Test fetching fills (may be empty)."""
        fills = client.get_fills(limit=10)
        assert isinstance(fills, list)
