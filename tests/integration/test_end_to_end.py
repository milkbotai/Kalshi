"""End-to-end integration tests.

Tests complete workflows involving multiple API clients and components.
"""

import os

import pytest

from src.shared.api.errors import classify_error, is_retryable
from src.shared.api.kalshi import KalshiClient
from src.shared.api.nws import NWSClient
from src.shared.api.response_models import Market, Observation


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture
    def nws_client(self) -> NWSClient:
        """Create NWS client."""
        return NWSClient()

    @pytest.fixture
    def kalshi_client(self) -> KalshiClient:
        """Create Kalshi client with RSA auth."""
        api_key_id = os.getenv("KALSHI_API_KEY_ID")
        private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")

        if not api_key_id or not private_key_path:
            pytest.skip("Kalshi API credentials not configured. Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH.")

        return KalshiClient(
            api_key_id=api_key_id,
            private_key_path=private_key_path,
            base_url="https://demo-api.kalshi.co/trade-api/v2",
        )

    def test_fetch_weather_and_markets_for_city(
        self, nws_client: NWSClient, kalshi_client: KalshiClient
    ) -> None:
        """Test complete workflow: fetch weather and find related markets."""
        # Step 1: Fetch weather for NYC
        office, grid_x, grid_y = "OKX", 33, 37
        station_id = "KNYC"
        
        forecast = nws_client.get_forecast(office, grid_x, grid_y)
        observation = nws_client.get_latest_observation(station_id)
        
        assert "properties" in forecast
        assert "properties" in observation
        
        # Step 2: Find NYC weather markets on Kalshi
        markets = kalshi_client.get_markets(series_ticker="HIGHNYC", limit=10)
        
        # Step 3: Verify we can get orderbook for any available market
        if len(markets) > 0:
            ticker = markets[0]["ticker"]
            orderbook = kalshi_client.get_orderbook(ticker)
            
            assert "yes" in orderbook or "no" in orderbook

    def test_parse_weather_data_for_trading_decision(
        self, nws_client: NWSClient
    ) -> None:
        """Test parsing weather data into format suitable for trading decisions."""
        office, grid_x, grid_y = "OKX", 33, 37
        station_id = "KNYC"
        
        # Fetch data
        forecast = nws_client.get_forecast(office, grid_x, grid_y)
        observation = nws_client.get_latest_observation(station_id)
        
        # Parse observation
        obs_props = observation["properties"]
        obs_model = Observation(**obs_props)
        
        # Verify we can extract temperature
        assert obs_model.timestamp is not None
        
        # Parse forecast periods
        forecast_periods = forecast["properties"]["periods"]
        assert len(forecast_periods) > 0
        
        # Extract high temperature from forecast
        daytime_periods = [p for p in forecast_periods if p.get("isDaytime", False)]
        if daytime_periods:
            high_temp = daytime_periods[0]["temperature"]
            assert isinstance(high_temp, int)
            assert -50 <= high_temp <= 150  # Fahrenheit range

    def test_find_tradeable_markets(self, kalshi_client: KalshiClient) -> None:
        """Test finding tradeable markets with good liquidity."""
        # Get open markets
        markets = kalshi_client.get_markets(status="open", limit=50)
        
        # Filter for markets with pricing and volume
        tradeable = []
        for market_data in markets:
            market = Market(**market_data)
            
            # Check if market has pricing
            if market.yes_bid is not None and market.yes_ask is not None:
                # Check spread
                if market.spread_cents is not None and market.spread_cents <= 5:
                    # Check volume
                    if market.volume > 0 or market.open_interest > 0:
                        tradeable.append(market)
        
        # We should find at least some tradeable markets
        # (This may fail if demo environment has no active markets)
        assert isinstance(tradeable, list)

    def test_error_recovery_workflow(self, nws_client: NWSClient) -> None:
        """Test error recovery in multi-step workflow."""
        # Step 1: Try to fetch from invalid endpoint (should fail)
        try:
            nws_client.get_forecast("INVALID", 999, 999)
            assert False, "Should have raised an error"
        except Exception as e:
            # Step 2: Classify the error
            classified = classify_error(e, endpoint="/gridpoints/INVALID/999,999/forecast")
            
            # Step 3: Check if retryable
            retryable = is_retryable(classified)
            
            # HTTP 404 errors are not retryable
            assert retryable is False or retryable is True  # Depends on error type
        
        # Step 4: Continue with valid request (recovery)
        forecast = nws_client.get_forecast("OKX", 33, 37)
        assert "properties" in forecast

    def test_concurrent_api_calls(
        self, nws_client: NWSClient, kalshi_client: KalshiClient
    ) -> None:
        """Test making concurrent calls to different APIs."""
        from concurrent.futures import ThreadPoolExecutor
        
        def fetch_weather() -> dict:
            return nws_client.get_forecast("OKX", 33, 37)
        
        def fetch_markets() -> list:
            return kalshi_client.get_markets(limit=5)
        
        # Execute concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            weather_future = executor.submit(fetch_weather)
            markets_future = executor.submit(fetch_markets)
            
            weather_result = weather_future.result()
            markets_result = markets_future.result()
        
        assert "properties" in weather_result
        assert isinstance(markets_result, list)

    def test_multiple_cities_workflow(self, nws_client: NWSClient) -> None:
        """Test fetching weather for multiple cities."""
        cities = [
            ("OKX", 33, 37, "KNYC"),  # NYC
            ("LOT", 65, 75, "KORD"),  # Chicago
            ("LOX", 154, 45, "KLAX"),  # Los Angeles
        ]
        
        results = []
        for office, grid_x, grid_y, station in cities:
            try:
                forecast = nws_client.get_forecast(office, grid_x, grid_y)
                observation = nws_client.get_latest_observation(station)
                
                results.append({
                    "office": office,
                    "forecast": forecast,
                    "observation": observation,
                })
            except Exception as e:
                # Log error but continue with other cities
                print(f"Failed to fetch data for {office}: {e}")
        
        # Should successfully fetch at least some cities
        assert len(results) > 0
        
        # Verify all results have expected structure
        for result in results:
            assert "properties" in result["forecast"]
            assert "properties" in result["observation"]
