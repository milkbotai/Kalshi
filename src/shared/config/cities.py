"""City configuration loader.

Loads city data from JSON file including NWS grid coordinates,
timezones, and settlement stations.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.shared.constants import CITY_CODES


class CityConfig(BaseModel):
    """Configuration for a single city.
    
    Contains all metadata needed for weather forecasting and trading
    including NWS grid coordinates and settlement stations.
    """

    code: str = Field(..., description="3-letter city code")
    name: str = Field(..., description="Full city name")
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")
    timezone: str = Field(..., description="IANA timezone identifier")
    cluster: str = Field(..., description="Geographic cluster for analysis")
    settlement_station: str = Field(..., description="ICAO code for settlement station")
    nws_office: str = Field(..., description="NWS office identifier")
    nws_grid_x: int = Field(..., ge=0, description="NWS grid X coordinate")
    nws_grid_y: int = Field(..., ge=0, description="NWS grid Y coordinate")
    forecast_url: str = Field(default="", description="NWS forecast URL")
    forecast_hourly_url: str = Field(default="", description="NWS hourly forecast URL")
    observation_stations_url: str = Field(default="", description="NWS observation stations URL")


class CityConfigLoader:
    """Loads and validates city configuration from JSON file."""

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize city config loader.
        
        Args:
            config_path: Path to cities.json file. If None, uses default location.
        """
        if config_path is None:
            config_path = Path("data/cities/cities.json")
        self.config_path = config_path
        self._cities: dict[str, CityConfig] = {}

    def load(self) -> dict[str, CityConfig]:
        """Load city configurations from JSON file.
        
        Returns:
            Dictionary mapping city codes to CityConfig objects
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid or missing required cities
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"City config file not found: {self.config_path}")

        with open(self.config_path) as f:
            data: dict[str, Any] = json.load(f)

        # Validate all required cities are present
        missing_cities = set(CITY_CODES) - set(data.keys())
        if missing_cities:
            raise ValueError(f"Missing city configurations: {missing_cities}")

        # Parse and validate each city config
        self._cities = {
            code: CityConfig(**city_data) for code, city_data in data.items()
        }

        return self._cities

    def get_city(self, code: str) -> CityConfig:
        """Get configuration for a specific city.
        
        Args:
            code: 3-letter city code
            
        Returns:
            CityConfig for the requested city
            
        Raises:
            KeyError: If city code is not found
        """
        if not self._cities:
            self.load()
        return self._cities[code]

    def get_all_cities(self) -> dict[str, CityConfig]:
        """Get all city configurations.
        
        Returns:
            Dictionary of all city configs
        """
        if not self._cities:
            self.load()
        return self._cities.copy()


# Global city config loader instance
city_loader = CityConfigLoader()
