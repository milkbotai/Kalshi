"""NWS (National Weather Service) API client.

Fetches weather forecasts and observations from weather.gov API.
Implements caching and rate limiting per NWS guidelines.
"""

import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.shared.config.logging import get_logger
from src.shared.constants import NWS_RATE_LIMIT_PER_SECOND

logger = get_logger(__name__)

# NWS API requires a User-Agent header
DEFAULT_USER_AGENT = "Milkbot/1.0 (contact@milkbot.ai)"


class NWSClient:
    """Client for National Weather Service API.
    
    Handles forecast and observation data retrieval with automatic
    retries and rate limiting.
    """

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT) -> None:
        """Initialize NWS API client.
        
        Args:
            user_agent: User-Agent string for API requests
        """
        self.base_url = "https://api.weather.gov"
        self.user_agent = user_agent
        self._last_request_time = 0.0
        
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        logger.info("nws_client_initialized", user_agent=user_agent)

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests.
        
        NWS recommends no more than 1 request per second.
        """
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / NWS_RATE_LIMIT_PER_SECOND
        
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug("rate_limit_sleep", sleep_seconds=sleep_time)
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()

    def _make_request(self, endpoint: str) -> dict[str, Any]:
        """Make HTTP request to NWS API.
        
        Args:
            endpoint: API endpoint path (without base URL)
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.HTTPError: If request fails after retries
        """
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/geo+json",
        }
        
        logger.debug("nws_request", url=url)
        
        try:
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            logger.debug("nws_request_success", url=url, status=response.status_code)
            return response.json()
            
        except requests.HTTPError as e:
            logger.error(
                "nws_request_failed",
                url=url,
                status=e.response.status_code if e.response else None,
                error=str(e),
            )
            raise
        except requests.RequestException as e:
            logger.error("nws_request_error", url=url, error=str(e))
            raise

    def get_forecast(self, office: str, grid_x: int, grid_y: int) -> dict[str, Any]:
        """Get forecast for a grid point.
        
        Args:
            office: NWS office identifier (e.g., "OKX")
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
            
        Returns:
            Forecast data including periods with temperature, conditions, etc.
            
        Example:
            >>> client = NWSClient()
            >>> forecast = client.get_forecast("OKX", 33, 37)
            >>> periods = forecast["properties"]["periods"]
        """
        endpoint = f"/gridpoints/{office}/{grid_x},{grid_y}/forecast"
        
        logger.info(
            "fetching_nws_forecast",
            office=office,
            grid_x=grid_x,
            grid_y=grid_y,
        )
        
        data = self._make_request(endpoint)
        return data

    def get_forecast_hourly(
        self, office: str, grid_x: int, grid_y: int
    ) -> dict[str, Any]:
        """Get hourly forecast for a grid point.
        
        Args:
            office: NWS office identifier
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
            
        Returns:
            Hourly forecast data
        """
        endpoint = f"/gridpoints/{office}/{grid_x},{grid_y}/forecast/hourly"
        
        logger.info(
            "fetching_nws_hourly_forecast",
            office=office,
            grid_x=grid_x,
            grid_y=grid_y,
        )
        
        data = self._make_request(endpoint)
        return data

    def get_observation_stations(
        self, office: str, grid_x: int, grid_y: int
    ) -> dict[str, Any]:
        """Get observation stations for a grid point.
        
        Args:
            office: NWS office identifier
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
            
        Returns:
            List of observation station URLs
        """
        endpoint = f"/gridpoints/{office}/{grid_x},{grid_y}/stations"
        
        logger.debug(
            "fetching_observation_stations",
            office=office,
            grid_x=grid_x,
            grid_y=grid_y,
        )
        
        data = self._make_request(endpoint)
        return data

    def get_latest_observation(self, station_id: str) -> dict[str, Any]:
        """Get latest observation from a station.
        
        Args:
            station_id: Station identifier (e.g., "KNYC")
            
        Returns:
            Latest observation data including temperature, conditions, etc.
            
        Example:
            >>> client = NWSClient()
            >>> obs = client.get_latest_observation("KNYC")
            >>> temp = obs["properties"]["temperature"]["value"]
        """
        endpoint = f"/stations/{station_id}/observations/latest"
        
        logger.info("fetching_latest_observation", station_id=station_id)
        
        data = self._make_request(endpoint)
        return data

    def get_point_metadata(self, lat: float, lon: float) -> dict[str, Any]:
        """Get metadata for a lat/lon point.
        
        Useful for discovering grid coordinates and forecast office.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Point metadata including grid coordinates and office
            
        Example:
            >>> client = NWSClient()
            >>> meta = client.get_point_metadata(40.7128, -74.0060)
            >>> office = meta["properties"]["gridId"]
            >>> grid_x = meta["properties"]["gridX"]
            >>> grid_y = meta["properties"]["gridY"]
        """
        endpoint = f"/points/{lat},{lon}"
        
        logger.info("fetching_point_metadata", lat=lat, lon=lon)
        
        data = self._make_request(endpoint)
        return data
