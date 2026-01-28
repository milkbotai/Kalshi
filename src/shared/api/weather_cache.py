"""Weather data cache layer with TTL and staleness detection.

Implements a per-city cache for NWS weather data with configurable TTL.
Thread-safe using locks for concurrent access.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from src.shared.api.nws import NWSClient
from src.shared.api.response_models import Forecast, ForecastPeriod, Observation
from src.shared.config.cities import CityConfig, city_loader
from src.shared.config.logging import get_logger
from src.shared.constants import WEATHER_CACHE_MIN

logger = get_logger(__name__)

# Staleness threshold (data older than this is marked as stale but still usable)
STALENESS_THRESHOLD_MIN = 15


@dataclass
class CachedWeather:
    """Cached weather data with metadata.

    Attributes:
        city_code: City code for this data
        forecast: Parsed forecast data
        observation: Parsed observation data
        fetched_at: When data was fetched
        is_stale: Whether data is older than staleness threshold
    """

    city_code: str
    forecast: dict[str, Any] | None = None
    observation: dict[str, Any] | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_stale: bool = False

    def age_seconds(self) -> float:
        """Get age of cached data in seconds.

        Returns:
            Age in seconds
        """
        now = datetime.now(timezone.utc)
        return (now - self.fetched_at).total_seconds()

    def age_minutes(self) -> float:
        """Get age of cached data in minutes.

        Returns:
            Age in minutes
        """
        return self.age_seconds() / 60.0


class WeatherCache:
    """Thread-safe weather data cache with TTL.

    Caches NWS forecast and observation data per city with automatic
    expiration and staleness detection.
    """

    def __init__(
        self,
        nws_client: NWSClient | None = None,
        ttl_minutes: int = WEATHER_CACHE_MIN,
        staleness_threshold_minutes: int = STALENESS_THRESHOLD_MIN,
    ) -> None:
        """Initialize weather cache.

        Args:
            nws_client: NWS API client (created if not provided)
            ttl_minutes: Cache TTL in minutes (default from WEATHER_CACHE_MIN)
            staleness_threshold_minutes: Age threshold for staleness flag
        """
        self.nws_client = nws_client or NWSClient()
        self.ttl_minutes = ttl_minutes
        self.staleness_threshold_minutes = staleness_threshold_minutes
        self._cache: dict[str, CachedWeather] = {}
        self._lock = threading.RLock()

        logger.info(
            "weather_cache_initialized",
            ttl_minutes=ttl_minutes,
            staleness_threshold=staleness_threshold_minutes,
        )

    def get_weather(
        self,
        city_code: str,
        force_refresh: bool = False,
    ) -> CachedWeather:
        """Get weather data for a city, using cache if fresh.

        Args:
            city_code: City code (e.g., "NYC")
            force_refresh: Force refresh from API even if cache is fresh

        Returns:
            CachedWeather with forecast and observation data

        Raises:
            KeyError: If city code is invalid
            requests.HTTPError: If API request fails
        """
        with self._lock:
            # Check cache
            cached = self._cache.get(city_code)

            if cached and not force_refresh:
                age = cached.age_minutes()

                # Cache hit - return if within TTL
                if age < self.ttl_minutes:
                    # Update staleness flag
                    cached.is_stale = age >= self.staleness_threshold_minutes

                    logger.debug(
                        "weather_cache_hit",
                        city_code=city_code,
                        age_minutes=round(age, 1),
                        is_stale=cached.is_stale,
                    )
                    return cached

                logger.debug(
                    "weather_cache_expired",
                    city_code=city_code,
                    age_minutes=round(age, 1),
                )

            # Cache miss or expired - fetch fresh data
            logger.info("weather_cache_miss", city_code=city_code)
            return self._fetch_and_cache(city_code)

    def _fetch_and_cache(self, city_code: str) -> CachedWeather:
        """Fetch weather data from NWS and cache it.

        Args:
            city_code: City code

        Returns:
            Fresh CachedWeather data
        """
        # Get city configuration
        city = city_loader.get_city(city_code)

        # Fetch forecast
        forecast = None
        try:
            raw_forecast = self.nws_client.get_forecast(
                city.nws_office,
                city.nws_grid_x,
                city.nws_grid_y,
            )
            forecast = raw_forecast.get("properties", {})
        except Exception as e:
            logger.warning(
                "forecast_fetch_failed",
                city_code=city_code,
                error=str(e),
            )

        # Fetch observation
        observation = None
        try:
            raw_observation = self.nws_client.get_latest_observation(
                city.settlement_station
            )
            observation = raw_observation.get("properties", {})
        except Exception as e:
            logger.warning(
                "observation_fetch_failed",
                city_code=city_code,
                station=city.settlement_station,
                error=str(e),
            )

        # Create cached entry
        cached = CachedWeather(
            city_code=city_code,
            forecast=forecast,
            observation=observation,
            fetched_at=datetime.now(timezone.utc),
            is_stale=False,
        )

        self._cache[city_code] = cached

        logger.info(
            "weather_data_cached",
            city_code=city_code,
            has_forecast=forecast is not None,
            has_observation=observation is not None,
        )

        return cached

    def invalidate(self, city_code: str) -> bool:
        """Invalidate cached data for a city.

        Args:
            city_code: City code to invalidate

        Returns:
            True if entry was removed, False if not found
        """
        with self._lock:
            if city_code in self._cache:
                del self._cache[city_code]
                logger.debug("weather_cache_invalidated", city_code=city_code)
                return True
            return False

    def invalidate_all(self) -> int:
        """Invalidate all cached data.

        Returns:
            Number of entries removed
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info("weather_cache_cleared", entries_removed=count)
            return count

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            stats = {
                "total_entries": len(self._cache),
                "ttl_minutes": self.ttl_minutes,
                "staleness_threshold_minutes": self.staleness_threshold_minutes,
                "entries": {},
            }

            for city_code, cached in self._cache.items():
                age = cached.age_minutes()
                stats["entries"][city_code] = {
                    "age_minutes": round(age, 1),
                    "is_stale": age >= self.staleness_threshold_minutes,
                    "is_expired": age >= self.ttl_minutes,
                    "has_forecast": cached.forecast is not None,
                    "has_observation": cached.observation is not None,
                }

            return stats

    def prefetch_all_cities(self) -> dict[str, bool]:
        """Prefetch weather data for all configured cities.

        Returns:
            Dictionary mapping city codes to success status
        """
        results: dict[str, bool] = {}
        cities = city_loader.get_all_cities()

        for city_code in cities:
            try:
                self.get_weather(city_code, force_refresh=True)
                results[city_code] = True
            except Exception as e:
                logger.warning(
                    "prefetch_failed",
                    city_code=city_code,
                    error=str(e),
                )
                results[city_code] = False

        logger.info(
            "prefetch_completed",
            total=len(results),
            success=sum(1 for v in results.values() if v),
        )

        return results


# Global weather cache instance
_weather_cache: WeatherCache | None = None


def get_weather_cache() -> WeatherCache:
    """Get or create global weather cache instance.

    Returns:
        WeatherCache singleton instance
    """
    global _weather_cache
    if _weather_cache is None:
        _weather_cache = WeatherCache()
    return _weather_cache


def get_weather(city_code: str, force_refresh: bool = False) -> CachedWeather:
    """Convenience function to get weather data.

    Args:
        city_code: City code
        force_refresh: Force refresh from API

    Returns:
        CachedWeather data
    """
    return get_weather_cache().get_weather(city_code, force_refresh)
