"""Unit tests for Kalshi API client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.shared.api.kalshi import KalshiClient


class TestKalshiClient:
    """Test suite for KalshiClient."""

    def test_client_initialization(self) -> None:
        """Test KalshiClient initializes with credentials."""
        client = KalshiClient(
            api_key="test_key",
            api_secret="test_secret",
            base_url="https://demo-api.kalshi.co/trade-api/v2",
        )

        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://demo-api.kalshi.co/trade-api/v2"
        assert client.session is not None

    @patch("src.shared.api.kalshi.time.sleep")
    @patch("src.shared.api.kalshi.time.time")
    def test_rate_limiting(self, mock_time: MagicMock, mock_sleep: MagicMock) -> None:
        """Test rate limiting enforces minimum interval between requests."""
        client = KalshiClient(api_key="test", api_secret="test")

        # Simulate rapid requests (10 req/sec = 0.1s interval)
        mock_time.side_effect = [1.0, 1.0, 1.05, 1.05]

        client._rate_limit()  # First request
        client._rate_limit()  # Second request should sleep

        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert 0.04 <= sleep_time <= 0.06  # Should sleep ~0.05s

    @patch("requests.Session.post")
    def test_authenticate_success(self, mock_post: MagicMock) -> None:
        """Test successful authentication."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test_token_123"}
        mock_post.return_value = mock_response

        client = KalshiClient(api_key="test_key", api_secret="test_secret")
        client._authenticate()

        assert client._access_token == "test_token_123"
        assert client._token_expiry > 0

        # Verify request payload
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["email"] == "test_key"
        assert call_args[1]["json"]["password"] == "test_secret"

    @patch("requests.Session.post")
    def test_authenticate_failure(self, mock_post: MagicMock) -> None:
        """Test authentication failure handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.HTTPError()
        mock_post.return_value = mock_response

        client = KalshiClient(api_key="bad_key", api_secret="bad_secret")

        with pytest.raises(requests.HTTPError):
            client._authenticate()

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_markets(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching markets."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "markets": [
                {
                    "ticker": "HIGHNYC-25JAN26",
                    "event_ticker": "HIGHNYC",
                    "status": "open",
                },
                {
                    "ticker": "HIGHNYC-26JAN26",
                    "event_ticker": "HIGHNYC",
                    "status": "open",
                },
            ]
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        markets = client.get_markets(series_ticker="HIGHNYC")

        assert len(markets) == 2
        assert markets[0]["ticker"] == "HIGHNYC-25JAN26"
        assert markets[1]["ticker"] == "HIGHNYC-26JAN26"

        # Verify request parameters
        call_args = mock_request.call_args
        assert call_args[1]["params"]["series_ticker"] == "HIGHNYC"
        assert call_args[1]["params"]["status"] == "open"

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_market(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching single market."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "market": {
                "ticker": "HIGHNYC-25JAN26",
                "title": "Will NYC high be above 32F?",
                "status": "open",
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        market = client.get_market("HIGHNYC-25JAN26")

        assert market["ticker"] == "HIGHNYC-25JAN26"
        assert market["status"] == "open"

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_orderbook(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching orderbook."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orderbook": {
                "yes": [{"price": 45, "count": 100}],
                "no": [{"price": 55, "count": 100}],
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        orderbook = client.get_orderbook("HIGHNYC-25JAN26")

        assert "yes" in orderbook
        assert "no" in orderbook
        assert orderbook["yes"][0]["price"] == 45
        assert orderbook["no"][0]["price"] == 55

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_create_order(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test creating an order."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "order": {
                "order_id": "order_123",
                "ticker": "HIGHNYC-25JAN26",
                "side": "yes",
                "action": "buy",
                "count": 10,
                "status": "resting",
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        order = client.create_order(
            ticker="HIGHNYC-25JAN26",
            side="yes",
            action="buy",
            count=10,
            yes_price=45,
            client_order_id="intent_123",
        )

        assert order["order_id"] == "order_123"
        assert order["status"] == "resting"

        # Verify request payload
        call_args = mock_request.call_args
        payload = call_args[1]["json"]
        assert payload["ticker"] == "HIGHNYC-25JAN26"
        assert payload["side"] == "yes"
        assert payload["action"] == "buy"
        assert payload["count"] == 10
        assert payload["yes_price"] == 45
        assert payload["client_order_id"] == "intent_123"

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_cancel_order(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test canceling an order."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"order_id": "order_123", "status": "canceled"}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        result = client.cancel_order("order_123")

        assert result["order_id"] == "order_123"
        assert result["status"] == "canceled"

        # Verify DELETE request
        call_args = mock_request.call_args
        assert call_args[1]["method"] == "DELETE"
        assert "/portfolio/orders/order_123" in call_args[0][0]

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_positions(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching positions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "positions": [
                {
                    "ticker": "HIGHNYC-25JAN26",
                    "position": 10,
                    "total_cost": 450,
                }
            ]
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        positions = client.get_positions()

        assert len(positions) == 1
        assert positions[0]["ticker"] == "HIGHNYC-25JAN26"
        assert positions[0]["position"] == 10

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_fills(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching fills."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "fills": [
                {
                    "order_id": "order_123",
                    "ticker": "HIGHNYC-25JAN26",
                    "count": 10,
                    "price": 45,
                    "created_time": "2026-01-25T12:00:00Z",
                }
            ]
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        fills = client.get_fills(ticker="HIGHNYC-25JAN26")

        assert len(fills) == 1
        assert fills[0]["order_id"] == "order_123"
        assert fills[0]["count"] == 10
        assert fills[0]["price"] == 45

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_balance(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching balance."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance": {"balance": 5000}}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        balance = client.get_balance()

        assert balance["balance"] == 5000

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_retry_on_server_error(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test automatic retry on server errors."""
        # First two calls fail, third succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 503

        http_error = requests.HTTPError()
        http_error.response = mock_response_fail
        mock_response_fail.raise_for_status.side_effect = http_error

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"markets": []}

        mock_request.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]

        with patch("src.shared.api.kalshi.time.sleep"):
            client = KalshiClient(api_key="test", api_secret="test")
            markets = client.get_markets()

            assert markets == []
            assert mock_request.call_count == 3

    @patch("requests.Session.request")
    @patch("requests.Session.post")
    def test_reauthenticate_on_401(self, mock_post: MagicMock, mock_request: MagicMock) -> None:
        """Test re-authentication on 401 error."""
        # First request fails with 401, second succeeds after re-auth
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401

        http_error = requests.HTTPError()
        http_error.response = mock_response_401
        mock_response_401.raise_for_status.side_effect = http_error

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"markets": []}

        mock_request.side_effect = [mock_response_401, mock_response_success]

        # Mock authentication response
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "new_token"}
        mock_post.return_value = mock_auth_response

        client = KalshiClient(api_key="test", api_secret="test")
        client._access_token = "old_token"  # Set expired token

        markets = client.get_markets()

        assert markets == []
        assert mock_request.call_count == 2
        assert mock_post.call_count == 2  # Initial auth + re-auth on 401

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_market_http_error(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test get_market handles HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")

        with pytest.raises(requests.HTTPError):
            client.get_market("INVALID-TICKER")

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_create_order_http_error(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test create_order handles HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 400

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")

        with pytest.raises(requests.HTTPError):
            client.create_order(
                ticker="HIGHNYC-25JAN26",
                side="yes",
                action="buy",
                count=10,
                yes_price=45,
            )

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_balance_http_error(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test get_balance handles HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")

        with pytest.raises(requests.HTTPError):
            client.get_balance()

    @patch("requests.Session.request")
    def test_request_timeout(self, mock_request: MagicMock) -> None:
        """Test request timeout handling."""
        mock_request.side_effect = requests.Timeout("Request timed out")

        client = KalshiClient(api_key="test", api_secret="test")
        client._access_token = "test_token"  # Skip auth

        with pytest.raises(requests.Timeout):
            client.get_markets()
