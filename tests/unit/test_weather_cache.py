"""Unit tests for weather cache layer.

Tests cache hit/miss behavior, TTL, staleness detection, and thread safety.
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.api.weather_cache import (
    STALENESS_THRESHOLD_MIN,
    CachedWeather,
    WeatherCache,
    get_weather,
    get_weather_cache,
)
from src.shared.constants import WEATHER_CACHE_MIN


class TestCachedWeather:
    """Tests for CachedWeather dataclass."""

    def test_cached_weather_creation(self) -> None:
        """Test creating a CachedWeather instance."""
        cached = CachedWeather(
            city_code="NYC",
            forecast={"periods": []},
            observation={"temperature": 20.0},
        )

        assert cached.city_code == "NYC"
        assert cached.forecast == {"periods": []}
        assert cached.observation == {"temperature": 20.0}
        assert cached.is_stale is False
        assert cached.fetched_at is not None

    def test_cached_weather_age_seconds(self) -> None:
        """Test age calculation in seconds."""
        # Create entry 5 seconds ago
        past = datetime.now(timezone.utc) - timedelta(seconds=5)
        cached = CachedWeather(city_code="NYC", fetched_at=past)

        age = cached.age_seconds()
        assert 4.5 <= age <= 6.0  # Allow some tolerance

    def test_cached_weather_age_minutes(self) -> None:
        """Test age calculation in minutes."""
        # Create entry 2 minutes ago
        past = datetime.now(timezone.utc) - timedelta(minutes=2)
        cached = CachedWeather(city_code="NYC", fetched_at=past)

        age = cached.age_minutes()
        assert 1.9 <= age <= 2.2  # Allow some tolerance


class TestWeatherCache:
    """Tests for WeatherCache class."""

    @pytest.fixture
    def mock_nws_client(self) -> MagicMock:
        """Create mock NWS client."""
        client = MagicMock()
        client.get_forecast.return_value = {
            "properties": {
                "periods": [
                    {"name": "Tonight", "temperature": 32},
                    {"name": "Tomorrow", "temperature": 45},
                ]
            }
        }
        client.get_latest_observation.return_value = {
            "properties": {
                "timestamp": "2026-01-27T12:00:00Z",
                "temperature": {"value": 5.0},
            }
        }
        return client

    @pytest.fixture
    def mock_city_loader(self) -> MagicMock:
        """Create mock city loader."""
        mock_city = MagicMock()
        mock_city.nws_office = "OKX"
        mock_city.nws_grid_x = 33
        mock_city.nws_grid_y = 37
        mock_city.settlement_station = "KNYC"

        mock_loader = MagicMock()
        mock_loader.get_city.return_value = mock_city
        mock_loader.get_all_cities.return_value = {"NYC": mock_city}

        return mock_loader

    def test_cache_initialization(self, mock_nws_client: MagicMock) -> None:
        """Test cache initialization with custom TTL."""
        cache = WeatherCache(
            nws_client=mock_nws_client,
            ttl_minutes=10,
            staleness_threshold_minutes=20,
        )

        assert cache.ttl_minutes == 10
        assert cache.staleness_threshold_minutes == 20
        assert cache.nws_client is mock_nws_client

    def test_cache_default_ttl(self) -> None:
        """Test cache uses default TTL from constants."""
        cache = WeatherCache()

        assert cache.ttl_minutes == WEATHER_CACHE_MIN
        assert cache.staleness_threshold_minutes == STALENESS_THRESHOLD_MIN

    @patch("src.shared.api.weather_cache.city_loader")
    def test_cache_miss_fetches_data(
        self,
        mock_loader: MagicMock,
        mock_nws_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test cache miss triggers API fetch."""
        mock_loader.get_city = mock_city_loader.get_city

        cache = WeatherCache(nws_client=mock_nws_client)
        result = cache.get_weather("NYC")

        assert result.city_code == "NYC"
        assert result.forecast is not None
        assert result.observation is not None
        mock_nws_client.get_forecast.assert_called_once()
        mock_nws_client.get_latest_observation.assert_called_once()

    @patch("src.shared.api.weather_cache.city_loader")
    def test_cache_hit_returns_cached_data(
        self,
        mock_loader: MagicMock,
        mock_nws_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test cache hit returns cached data without API call."""
        mock_loader.get_city = mock_city_loader.get_city

        cache = WeatherCache(nws_client=mock_nws_client, ttl_minutes=5)

        # First call - cache miss
        result1 = cache.get_weather("NYC")
        assert mock_nws_client.get_forecast.call_count == 1

        # Second call - cache hit
        result2 = cache.get_weather("NYC")
        assert mock_nws_client.get_forecast.call_count == 1  # No new call

        assert result1.fetched_at == result2.fetched_at

    @patch("src.shared.api.weather_cache.city_loader")
    def test_cache_expires_after_ttl(
        self,
        mock_loader: MagicMock,
        mock_nws_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test cache expires and refetches after TTL."""
        mock_loader.get_city = mock_city_loader.get_city

        # Very short TTL for testing
        cache = WeatherCache(nws_client=mock_nws_client, ttl_minutes=0.001)

        # First call - cache miss
        result1 = cache.get_weather("NYC")
        assert mock_nws_client.get_forecast.call_count == 1

        # Wait for expiration
        time.sleep(0.1)

        # Second call - cache expired, refetch
        result2 = cache.get_weather("NYC")
        assert mock_nws_client.get_forecast.call_count == 2  # New call

        assert result2.fetched_at > result1.fetched_at

    @patch("src.shared.api.weather_cache.city_loader")
    def test_staleness_flag_set(
        self,
        mock_loader: MagicMock,
        mock_nws_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test staleness flag is set for old but valid cache entries."""
        mock_loader.get_city = mock_city_loader.get_city

        # TTL 10 minutes, staleness at 0.001 minutes (immediate)
        cache = WeatherCache(
            nws_client=mock_nws_client,
            ttl_minutes=10,
            staleness_threshold_minutes=0.001,
        )

        # First call - fresh
        result1 = cache.get_weather("NYC")
        assert result1.is_stale is False

        # Wait a tiny bit
        time.sleep(0.1)

        # Second call - still within TTL but stale
        result2 = cache.get_weather("NYC")
        assert result2.is_stale is True

    @patch("src.shared.api.weather_cache.city_loader")
    def test_force_refresh_bypasses_cache(
        self,
        mock_loader: MagicMock,
        mock_nws_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test force_refresh always fetches from API."""
        mock_loader.get_city = mock_city_loader.get_city

        cache = WeatherCache(nws_client=mock_nws_client, ttl_minutes=60)

        # First call
        cache.get_weather("NYC")
        assert mock_nws_client.get_forecast.call_count == 1

        # Force refresh
        cache.get_weather("NYC", force_refresh=True)
        assert mock_nws_client.get_forecast.call_count == 2

    @patch("src.shared.api.weather_cache.city_loader")
    def test_invalidate_removes_entry(
        self,
        mock_loader: MagicMock,
        mock_nws_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test invalidate removes specific cache entry."""
        mock_loader.get_city = mock_city_loader.get_city

        cache = WeatherCache(nws_client=mock_nws_client)

        # Populate cache
        cache.get_weather("NYC")
        assert mock_nws_client.get_forecast.call_count == 1

        # Invalidate
        result = cache.invalidate("NYC")
        assert result is True

        # Next call should fetch again
        cache.get_weather("NYC")
        assert mock_nws_client.get_forecast.call_count == 2

    def test_invalidate_nonexistent_entry(self, mock_nws_client: MagicMock) -> None:
        """Test invalidate returns False for nonexistent entry."""
        cache = WeatherCache(nws_client=mock_nws_client)

        result = cache.invalidate("NONEXISTENT")
        assert result is False

    @patch("src.shared.api.weather_cache.city_loader")
    def test_invalidate_all_clears_cache(
        self,
        mock_loader: MagicMock,
        mock_nws_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test invalidate_all clears entire cache."""
        mock_loader.get_city = mock_city_loader.get_city

        cache = WeatherCache(nws_client=mock_nws_client)

        # Populate cache
        cache.get_weather("NYC")

        # Clear all
        count = cache.invalidate_all()
        assert count == 1

        # Verify stats
        stats = cache.get_cache_stats()
        assert stats["total_entries"] == 0

    @patch("src.shared.api.weather_cache.city_loader")
    def test_cache_stats(
        self,
        mock_loader: MagicMock,
        mock_nws_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test cache statistics."""
        mock_loader.get_city = mock_city_loader.get_city

        cache = WeatherCache(nws_client=mock_nws_client, ttl_minutes=5)

        # Populate cache
        cache.get_weather("NYC")

        stats = cache.get_cache_stats()

        assert stats["total_entries"] == 1
        assert stats["ttl_minutes"] == 5
        assert "NYC" in stats["entries"]
        assert stats["entries"]["NYC"]["has_forecast"] is True
        assert stats["entries"]["NYC"]["has_observation"] is True

    @patch("src.shared.api.weather_cache.city_loader")
    def test_handles_forecast_fetch_failure(
        self,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test cache handles forecast fetch failure gracefully."""
        mock_loader.get_city = mock_city_loader.get_city

        mock_client = MagicMock()
        mock_client.get_forecast.side_effect = Exception("API Error")
        mock_client.get_latest_observation.return_value = {
            "properties": {"temperature": {"value": 5.0}}
        }

        cache = WeatherCache(nws_client=mock_client)
        result = cache.get_weather("NYC")

        assert result.forecast is None
        assert result.observation is not None

    @patch("src.shared.api.weather_cache.city_loader")
    def test_handles_observation_fetch_failure(
        self,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test cache handles observation fetch failure gracefully."""
        mock_loader.get_city = mock_city_loader.get_city

        mock_client = MagicMock()
        mock_client.get_forecast.return_value = {"properties": {"periods": []}}
        mock_client.get_latest_observation.side_effect = Exception("API Error")

        cache = WeatherCache(nws_client=mock_client)
        result = cache.get_weather("NYC")

        assert result.forecast is not None
        assert result.observation is None


class TestWeatherCacheThreadSafety:
    """Tests for thread safety of WeatherCache."""

    @patch("src.shared.api.weather_cache.city_loader")
    def test_concurrent_access(
        self,
        mock_loader: MagicMock,
    ) -> None:
        """Test concurrent access doesn't cause race conditions."""
        mock_city = MagicMock()
        mock_city.nws_office = "OKX"
        mock_city.nws_grid_x = 33
        mock_city.nws_grid_y = 37
        mock_city.settlement_station = "KNYC"
        mock_loader.get_city.return_value = mock_city

        mock_client = MagicMock()
        mock_client.get_forecast.return_value = {"properties": {"periods": []}}
        mock_client.get_latest_observation.return_value = {"properties": {}}

        cache = WeatherCache(nws_client=mock_client, ttl_minutes=60)

        errors: list[Exception] = []
        results: list[CachedWeather] = []

        def fetch_weather() -> None:
            try:
                result = cache.get_weather("NYC")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Spawn multiple threads
        threads = [threading.Thread(target=fetch_weather) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10

        # All results should have same fetched_at (cache hit)
        fetched_times = {r.fetched_at for r in results}
        assert len(fetched_times) == 1  # Same cached entry returned


class TestGlobalWeatherCache:
    """Tests for global cache functions."""

    def test_get_weather_cache_singleton(self) -> None:
        """Test get_weather_cache returns singleton."""
        # Reset global cache for test
        import src.shared.api.weather_cache as cache_module

        cache_module._weather_cache = None

        cache1 = get_weather_cache()
        cache2 = get_weather_cache()

        assert cache1 is cache2

    @patch("src.shared.api.weather_cache.get_weather_cache")
    def test_get_weather_convenience_function(self, mock_get_cache: MagicMock) -> None:
        """Test get_weather convenience function."""
        mock_cache = MagicMock()
        mock_cache.get_weather.return_value = CachedWeather(city_code="NYC")
        mock_get_cache.return_value = mock_cache

        result = get_weather("NYC")

        assert result.city_code == "NYC"
        mock_cache.get_weather.assert_called_once_with("NYC", False)

    @patch("src.shared.api.weather_cache.get_weather_cache")
    def test_get_weather_with_force_refresh(self, mock_get_cache: MagicMock) -> None:
        """Test get_weather with force_refresh parameter."""
        mock_cache = MagicMock()
        mock_cache.get_weather.return_value = CachedWeather(city_code="NYC")
        mock_get_cache.return_value = mock_cache

        get_weather("NYC", force_refresh=True)

        mock_cache.get_weather.assert_called_once_with("NYC", True)
