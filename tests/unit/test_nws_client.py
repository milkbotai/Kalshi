"""Unit tests for NWS API client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.shared.api.nws import NWSClient


class TestNWSClient:
    """Test suite for NWSClient."""

    def test_client_initialization(self) -> None:
        """Test NWSClient initializes with default user agent."""
        client = NWSClient()
        
        assert client.base_url == "https://api.weather.gov"
        assert "Milkbot" in client.user_agent
        assert client.session is not None

    def test_client_custom_user_agent(self) -> None:
        """Test NWSClient accepts custom user agent."""
        custom_ua = "TestBot/1.0 (test@example.com)"
        client = NWSClient(user_agent=custom_ua)
        
        assert client.user_agent == custom_ua

    @patch("src.shared.api.nws.time.sleep")
    @patch("src.shared.api.nws.time.time")
    def test_rate_limiting(self, mock_time: MagicMock, mock_sleep: MagicMock) -> None:
        """Test rate limiting enforces minimum interval between requests."""
        client = NWSClient()
        
        # Simulate rapid requests
        mock_time.side_effect = [0.0, 0.5, 0.5]  # Second request too soon
        
        client._rate_limit()  # First request
        client._rate_limit()  # Second request should sleep
        
        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert sleep_time > 0

    @patch("requests.Session.get")
    def test_get_forecast_success(self, mock_get: MagicMock) -> None:
        """Test successful forecast retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {
                "periods": [
                    {
                        "number": 1,
                        "name": "Today",
                        "temperature": 72,
                        "temperatureUnit": "F",
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        client = NWSClient()
        result = client.get_forecast("OKX", 33, 37)
        
        assert "properties" in result
        assert "periods" in result["properties"]
        assert result["properties"]["periods"][0]["temperature"] == 72
        
        # Verify request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "/gridpoints/OKX/33,37/forecast" in call_args[0][0]
        assert call_args[1]["headers"]["User-Agent"] == client.user_agent

    @patch("requests.Session.get")
    def test_get_forecast_http_error(self, mock_get: MagicMock) -> None:
        """Test forecast retrieval handles HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError()
        mock_get.return_value = mock_response
        
        client = NWSClient()
        
        with pytest.raises(requests.HTTPError):
            client.get_forecast("INVALID", 0, 0)

    @patch("requests.Session.get")
    def test_get_forecast_hourly(self, mock_get: MagicMock) -> None:
        """Test hourly forecast retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {
                "periods": [
                    {"startTime": "2026-01-25T12:00:00-05:00", "temperature": 68}
                ]
            }
        }
        mock_get.return_value = mock_response
        
        client = NWSClient()
        result = client.get_forecast_hourly("OKX", 33, 37)
        
        assert "properties" in result
        assert len(result["properties"]["periods"]) > 0

    @patch("requests.Session.get")
    def test_get_latest_observation(self, mock_get: MagicMock) -> None:
        """Test latest observation retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {
                "temperature": {"value": 20.5, "unitCode": "wmoUnit:degC"},
                "timestamp": "2026-01-25T17:00:00+00:00",
            }
        }
        mock_get.return_value = mock_response
        
        client = NWSClient()
        result = client.get_latest_observation("KNYC")
        
        assert "properties" in result
        assert "temperature" in result["properties"]
        assert result["properties"]["temperature"]["value"] == 20.5
        
        # Verify correct endpoint
        call_args = mock_get.call_args
        assert "/stations/KNYC/observations/latest" in call_args[0][0]

    @patch("requests.Session.get")
    def test_get_observation_stations(self, mock_get: MagicMock) -> None:
        """Test observation stations retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {"properties": {"stationIdentifier": "KNYC"}},
                {"properties": {"stationIdentifier": "KLGA"}},
            ]
        }
        mock_get.return_value = mock_response
        
        client = NWSClient()
        result = client.get_observation_stations("OKX", 33, 37)
        
        assert "features" in result
        assert len(result["features"]) == 2

    @patch("requests.Session.get")
    def test_get_point_metadata(self, mock_get: MagicMock) -> None:
        """Test point metadata retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {
                "gridId": "OKX",
                "gridX": 33,
                "gridY": 37,
                "forecast": "https://api.weather.gov/gridpoints/OKX/33,37/forecast",
            }
        }
        mock_get.return_value = mock_response
        
        client = NWSClient()
        result = client.get_point_metadata(40.7128, -74.0060)
        
        assert result["properties"]["gridId"] == "OKX"
        assert result["properties"]["gridX"] == 33
        assert result["properties"]["gridY"] == 37

    @patch("requests.Session.get")
    def test_request_timeout(self, mock_get: MagicMock) -> None:
        """Test request timeout handling."""
        mock_get.side_effect = requests.Timeout("Request timed out")
        
        client = NWSClient()
        
        with pytest.raises(requests.Timeout):
            client.get_forecast("OKX", 33, 37)

    @patch("requests.Session.get")
    def test_retry_on_server_error(self, mock_get: MagicMock) -> None:
        """Test automatic retry on server errors."""
        # First two calls fail, third succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 503
        mock_response_fail.raise_for_status.side_effect = requests.HTTPError()
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"properties": {"periods": []}}
        
        mock_get.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]
        
        client = NWSClient()
        result = client.get_forecast("OKX", 33, 37)
        
        # Should succeed after retries
        assert "properties" in result
        assert mock_get.call_count == 3
