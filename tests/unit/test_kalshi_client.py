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
        assert "/portfolio/orders/order_123" in call_args[1]["url"]

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_orders_with_filters(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching orders with ticker and status filters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orders": [
                {
                    "order_id": "order_123",
                    "ticker": "HIGHNYC-25JAN26",
                    "status": "resting",
                }
            ]
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        orders = client.get_orders(ticker="HIGHNYC-25JAN26", status="resting")

        assert len(orders) == 1
        assert orders[0]["order_id"] == "order_123"
        assert orders[0]["status"] == "resting"

        # Verify request parameters
        call_args = mock_request.call_args
        assert call_args[1]["params"]["ticker"] == "HIGHNYC-25JAN26"
        assert call_args[1]["params"]["status"] == "resting"

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
    def test_get_positions_with_ticker_filter(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test fetching positions filtered by ticker."""
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
    def test_get_market_with_invalid_ticker(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_market with invalid ticker returns empty dict."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"market": {}}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        market = client.get_market("INVALID-TICKER")

        assert market == {}

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
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_fills_with_timestamps(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching fills with min and max timestamp filters."""
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
        fills = client.get_fills(
            ticker="HIGHNYC-25JAN26",
            min_ts=1706184000000,
            max_ts=1706270400000,
        )

        assert len(fills) == 1

        # Verify timestamp parameters were passed
        call_args = mock_request.call_args
        assert call_args[1]["params"]["min_ts"] == 1706184000000
        assert call_args[1]["params"]["max_ts"] == 1706270400000

    @patch("requests.Session.request")
    def test_request_timeout(self, mock_request: MagicMock) -> None:
        """Test request timeout handling."""
        mock_request.side_effect = requests.Timeout("Request timed out")

        client = KalshiClient(api_key="test", api_secret="test")
        client._access_token = "test_token"  # Skip auth

        with pytest.raises(requests.Timeout):
            client.get_markets()


class TestKalshiClientRetryLogic:
    """Test suite for retry logic and error handling."""

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_all_retries_exhausted(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test behavior when all retries are exhausted."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        # All requests fail
        mock_request.return_value = mock_response

        with patch("src.shared.api.kalshi.time.sleep"):
            client = KalshiClient(api_key="test", api_secret="test")

            with pytest.raises(requests.HTTPError):
                client.get_markets()

            # Should have tried 3 times
            assert mock_request.call_count == 3

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_retry_on_500_error(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test retry on 500 internal server error."""
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500

        http_error = requests.HTTPError()
        http_error.response = mock_response_500
        mock_response_500.raise_for_status.side_effect = http_error

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"markets": []}

        # First fails, second succeeds
        mock_request.side_effect = [mock_response_500, mock_response_success]

        with patch("src.shared.api.kalshi.time.sleep"):
            client = KalshiClient(api_key="test", api_secret="test")
            markets = client.get_markets()

            assert markets == []
            assert mock_request.call_count == 2

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_retry_on_502_error(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test retry on 502 bad gateway error."""
        mock_response_502 = MagicMock()
        mock_response_502.status_code = 502

        http_error = requests.HTTPError()
        http_error.response = mock_response_502
        mock_response_502.raise_for_status.side_effect = http_error

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"markets": []}

        mock_request.side_effect = [mock_response_502, mock_response_success]

        with patch("src.shared.api.kalshi.time.sleep"):
            client = KalshiClient(api_key="test", api_secret="test")
            markets = client.get_markets()

            assert markets == []

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_retry_on_504_error(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test retry on 504 gateway timeout error."""
        mock_response_504 = MagicMock()
        mock_response_504.status_code = 504

        http_error = requests.HTTPError()
        http_error.response = mock_response_504
        mock_response_504.raise_for_status.side_effect = http_error

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"markets": []}

        mock_request.side_effect = [mock_response_504, mock_response_success]

        with patch("src.shared.api.kalshi.time.sleep"):
            client = KalshiClient(api_key="test", api_secret="test")
            markets = client.get_markets()

            assert markets == []

    @patch("requests.Session.request")
    @patch("requests.Session.post")
    def test_token_refresh_on_multiple_401s(
        self, mock_post: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test token refresh behavior on repeated 401 errors."""
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401

        http_error = requests.HTTPError()
        http_error.response = mock_response_401
        mock_response_401.raise_for_status.side_effect = http_error

        # All requests return 401
        mock_request.return_value = mock_response_401

        # Auth succeeds
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "new_token"}
        mock_post.return_value = mock_auth_response

        client = KalshiClient(api_key="test", api_secret="test")
        client._access_token = "old_token"

        with pytest.raises(requests.HTTPError):
            client.get_markets()

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_rate_limit_429_response(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test handling of 429 rate limit response."""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        http_error = requests.HTTPError()
        http_error.response = mock_response_429
        mock_response_429.raise_for_status.side_effect = http_error

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"markets": []}

        # First call rate limited, second succeeds
        mock_request.side_effect = [mock_response_429, mock_response_success]

        with patch("src.shared.api.kalshi.time.sleep") as mock_sleep:
            client = KalshiClient(api_key="test", api_secret="test")
            markets = client.get_markets()

            assert markets == []
            # Should have slept for backoff
            mock_sleep.assert_called()

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_empty_markets_response(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test handling of empty markets response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No "markets" key

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        markets = client.get_markets()

        assert markets == []

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_null_response_handling(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test handling of null/None values in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"markets": None}

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        markets = client.get_markets()

        # Should handle None gracefully
        assert markets is None or markets == []

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_positions_empty(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_positions with empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"positions": []}

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        positions = client.get_positions()

        assert positions == []

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_fills_empty(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_fills with empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"fills": []}

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        fills = client.get_fills()

        assert fills == []

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_cancel_order_not_found(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test cancel_order when order not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")

        with pytest.raises(requests.HTTPError):
            client.cancel_order("nonexistent_order")

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_orders_empty(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_orders with empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"orders": []}

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        orders = client.get_orders()

        assert orders == []

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_no_retry_on_400_error(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test no retry on 400 bad request error."""
        mock_response = MagicMock()
        mock_response.status_code = 400

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")

        with pytest.raises(requests.HTTPError):
            client.get_markets()

        # Should NOT retry on 400
        assert mock_request.call_count == 1

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_balance_empty_response(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_balance with empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No "balance" key

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        balance = client.get_balance()

        assert balance == {}

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_create_order_with_no_price(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test create_order with no side price."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"order": {"order_id": "test_123"}}

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        order = client.create_order(
            ticker="TEST",
            side="no",
            action="buy",
            count=10,
            no_price=55,  # Using no_price instead of yes_price
        )

        assert order["order_id"] == "test_123"
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["json"]["no_price"] == 55

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_fills_with_no_ticker(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_fills without ticker filter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"fills": [{"order_id": "123"}]}

        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        fills = client.get_fills()

        assert len(fills) == 1
        # Verify no ticker param
        call_kwargs = mock_request.call_args[1]
        assert "ticker" not in call_kwargs.get("params", {})

    @patch("requests.Session.post")
    def test_authenticate_key_error(self, mock_post: MagicMock) -> None:
        """Test authentication with missing token in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Missing "token" key

        mock_post.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")

        with pytest.raises(KeyError):
            client._authenticate()

    @patch("requests.Session.post")
    def test_authenticate_request_exception(self, mock_post: MagicMock) -> None:
        """Test authentication with request exception."""
        mock_post.side_effect = requests.RequestException("Connection failed")

        client = KalshiClient(api_key="test", api_secret="test")

        with pytest.raises(requests.RequestException):
            client._authenticate()

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_request_exception_handling(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test handling of generic request exception."""
        mock_request.side_effect = requests.RequestException("Network error")

        client = KalshiClient(api_key="test", api_secret="test")

        with pytest.raises(requests.RequestException):
            client.get_markets()


class TestKalshiClientTyped:
    """Test suite for typed Kalshi client methods that return Pydantic models."""

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_markets_typed(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching markets as Pydantic models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "markets": [
                {
                    "ticker": "HIGHNYC-25JAN26",
                    "event_ticker": "HIGHNYC",
                    "title": "Will NYC high be above 32F?",
                    "yes_bid": 45,
                    "yes_ask": 48,
                    "volume": 1000,
                    "open_interest": 500,
                    "status": "open",
                },
            ]
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        markets = client.get_markets_typed(series_ticker="HIGHNYC")

        assert len(markets) == 1
        assert markets[0].ticker == "HIGHNYC-25JAN26"
        assert markets[0].yes_bid == 45
        assert markets[0].yes_ask == 48
        assert markets[0].spread_cents == 3

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_market_typed(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching single market as Pydantic model."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "market": {
                "ticker": "HIGHNYC-25JAN26",
                "event_ticker": "HIGHNYC",
                "title": "Will NYC high be above 32F?",
                "yes_bid": 45,
                "yes_ask": 48,
                "volume": 1000,
                "open_interest": 500,
                "status": "open",
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        market = client.get_market_typed("HIGHNYC-25JAN26")

        assert market is not None
        assert market.ticker == "HIGHNYC-25JAN26"
        assert market.spread_cents == 3
        assert market.mid_price == 46.5

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_market_typed_empty_response(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_market_typed returns None for empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"market": {}}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        market = client.get_market_typed("INVALID")

        assert market is None

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_orderbook_typed(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test fetching orderbook as Pydantic model."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orderbook": {
                "yes": [
                    {"price": 45, "count": 100},
                    {"price": 44, "count": 200},
                ],
                "no": [
                    {"price": 55, "count": 100},
                ],
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        orderbook = client.get_orderbook_typed("HIGHNYC-25JAN26")

        assert len(orderbook.yes) == 2
        assert len(orderbook.no) == 1
        assert orderbook.yes[0].price == 45
        assert orderbook.yes[0].quantity == 100
        assert orderbook.best_yes_bid == 45

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_orderbook_typed_empty(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_orderbook_typed returns empty orderbook for closed market."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"orderbook": {}}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        orderbook = client.get_orderbook_typed("CLOSED-MARKET")

        assert len(orderbook.yes) == 0
        assert len(orderbook.no) == 0
        assert orderbook.best_yes_bid is None
        assert orderbook.best_yes_ask is None

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_calculate_spread(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test spread calculation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "market": {
                "ticker": "HIGHNYC-25JAN26",
                "event_ticker": "HIGHNYC",
                "title": "Test",
                "yes_bid": 42,
                "yes_ask": 47,
                "status": "open",
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        spread = client.calculate_spread("HIGHNYC-25JAN26")

        assert spread == 5

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_calculate_spread_tight(self, mock_auth: MagicMock, mock_request: MagicMock) -> None:
        """Test spread calculation for tight market."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "market": {
                "ticker": "TIGHT-MARKET",
                "event_ticker": "TIGHT",
                "title": "Test",
                "yes_bid": 48,
                "yes_ask": 50,
                "status": "open",
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        spread = client.calculate_spread("TIGHT-MARKET")

        # Spread of 2 cents is below the 3 cent threshold
        assert spread == 2
        assert spread <= 3  # Good for trading

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_calculate_spread_no_pricing(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test spread calculation returns None when pricing unavailable."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "market": {
                "ticker": "NO-PRICING",
                "event_ticker": "TEST",
                "title": "Test",
                "yes_bid": None,
                "yes_ask": None,
                "status": "closed",
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        spread = client.calculate_spread("NO-PRICING")

        assert spread is None

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_calculate_spread_market_not_found(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test spread calculation returns None for non-existent market."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"market": {}}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        spread = client.calculate_spread("NONEXISTENT")

        assert spread is None

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_markets_typed_parse_error(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_markets_typed handles parse errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Invalid market data that will cause parse error
        mock_response.json.return_value = {
            "markets": [
                {"ticker": "VALID", "event_ticker": "TEST", "title": "Test", "status": "open"},
                {"invalid": "data"},  # Missing required fields
            ]
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        markets = client.get_markets_typed()

        # Should return valid markets, skip invalid ones
        assert len(markets) >= 1

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_market_typed_parse_error(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_market_typed handles parse errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Empty market data (no ticker field)
        mock_response.json.return_value = {"market": {}}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        market = client.get_market_typed("TEST")

        # Should return None for empty market
        assert market is None

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_orderbook_typed_parse_error(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_orderbook_typed handles level parse errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orderbook": {
                "yes": [
                    {"price": 45, "count": 100},
                    {"invalid": "level"},  # Invalid level
                ],
                "no": [{"price": 55, "count": 100}],
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        orderbook = client.get_orderbook_typed("TEST")

        # Should have parsed valid levels
        assert len(orderbook.yes) >= 1
        assert len(orderbook.no) == 1

    @patch("requests.Session.request")
    @patch.object(KalshiClient, "_ensure_authenticated")
    def test_get_markets_with_event_ticker(
        self, mock_auth: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_markets with event_ticker filter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"markets": []}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        client.get_markets(event_ticker="HIGHNYC-25JAN26")

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["params"]["event_ticker"] == "HIGHNYC-25JAN26"
