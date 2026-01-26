"""Integration tests for NWS API client.

These tests make real API calls to weather.gov and are marked as integration tests.
They can be skipped in CI if needed using: pytest -m "not integration"
"""

import pytest

from src.shared.api.nws import NWSClient
from src.shared.api.response_models import ForecastPeriod, Observation


@pytest.mark.integration
@pytest.mark.slow
class TestNWSIntegration:
    """Integration tests for NWS API client with real API calls."""

    @pytest.fixture
    def nws_client(self) -> NWSClient:
        """Create NWS client for testing."""
        return NWSClient()

    def test_get_point_metadata_nyc(self, nws_client: NWSClient) -> None:
        """Test fetching point metadata for NYC coordinates."""
        # NYC coordinates
        lat, lon = 40.7128, -74.0060

        result = nws_client.get_point_metadata(lat, lon)

        assert "properties" in result
        assert "gridId" in result["properties"]
        assert "gridX" in result["properties"]
        assert "gridY" in result["properties"]
        
        # NYC should be in OKX office
        assert result["properties"]["gridId"] == "OKX"

    def test_get_forecast_nyc(self, nws_client: NWSClient) -> None:
        """Test fetching forecast for NYC grid point."""
        # NYC grid coordinates
        office, grid_x, grid_y = "OKX", 33, 37

        result = nws_client.get_forecast(office, grid_x, grid_y)

        assert "properties" in result
        assert "periods" in result["properties"]
        assert len(result["properties"]["periods"]) > 0
        
        # Verify first period has expected fields
        first_period = result["properties"]["periods"][0]
        assert "temperature" in first_period
        assert "shortForecast" in first_period
        assert "detailedForecast" in first_period

    def test_get_forecast_hourly_nyc(self, nws_client: NWSClient) -> None:
        """Test fetching hourly forecast for NYC."""
        office, grid_x, grid_y = "OKX", 33, 37

        result = nws_client.get_forecast_hourly(office, grid_x, grid_y)

        assert "properties" in result
        assert "periods" in result["properties"]
        
        # Hourly forecast should have many periods
        assert len(result["properties"]["periods"]) >= 24

    def test_get_latest_observation_nyc(self, nws_client: NWSClient) -> None:
        """Test fetching latest observation from NYC station."""
        station_id = "KNYC"

        result = nws_client.get_latest_observation(station_id)

        assert "properties" in result
        assert "timestamp" in result["properties"]
        assert "temperature" in result["properties"]

    def test_get_observation_stations_nyc(self, nws_client: NWSClient) -> None:
        """Test fetching observation stations for NYC grid."""
        office, grid_x, grid_y = "OKX", 33, 37

        result = nws_client.get_observation_stations(office, grid_x, grid_y)

        assert "features" in result
        assert len(result["features"]) > 0
        
        # Verify stations have identifiers
        first_station = result["features"][0]
        assert "properties" in first_station
        assert "stationIdentifier" in first_station["properties"]

    def test_rate_limiting_enforced(self, nws_client: NWSClient) -> None:
        """Test that rate limiting is enforced across multiple requests."""
        import time
        
        office, grid_x, grid_y = "OKX", 33, 37
        
        # Make two rapid requests
        start = time.time()
        nws_client.get_forecast(office, grid_x, grid_y)
        nws_client.get_forecast(office, grid_x, grid_y)
        elapsed = time.time() - start
        
        # Should take at least 1 second due to rate limiting (1 req/sec)
        assert elapsed >= 1.0

    def test_parse_forecast_with_pydantic(self, nws_client: NWSClient) -> None:
        """Test parsing NWS forecast response with Pydantic models."""
        office, grid_x, grid_y = "OKX", 33, 37

        result = nws_client.get_forecast(office, grid_x, grid_y)
        
        # Parse with Pydantic model
        properties = result["properties"]
        
        # Parse individual periods
        periods = [
            ForecastPeriod(**period) for period in properties["periods"][:3]
        ]
        
        assert len(periods) == 3
        assert all(isinstance(p, ForecastPeriod) for p in periods)
        assert all(p.temperature > -100 and p.temperature < 150 for p in periods)

    def test_parse_observation_with_pydantic(self, nws_client: NWSClient) -> None:
        """Test parsing NWS observation response with Pydantic models."""
        station_id = "KNYC"

        result = nws_client.get_latest_observation(station_id)
        
        # Parse with Pydantic model
        properties = result["properties"]
        observation = Observation(**properties)
        
        assert isinstance(observation, Observation)
        assert observation.timestamp is not None
        
        # Temperature might be None if not available
        if observation.temperature is not None:
            assert -50 <= observation.temperature <= 50  # Celsius range

    def test_error_handling_invalid_grid(self, nws_client: NWSClient) -> None:
        """Test error handling for invalid grid coordinates."""
        # Invalid grid coordinates
        office, grid_x, grid_y = "INVALID", 999, 999

        with pytest.raises(Exception):  # Will raise HTTPError or similar
            nws_client.get_forecast(office, grid_x, grid_y)

    def test_error_handling_invalid_station(self, nws_client: NWSClient) -> None:
        """Test error handling for invalid station ID."""
        station_id = "INVALID"

        with pytest.raises(Exception):  # Will raise HTTPError or similar
            nws_client.get_latest_observation(station_id)
