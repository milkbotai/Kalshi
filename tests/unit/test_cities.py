"""Unit tests for city configuration loader."""

import json
from pathlib import Path

import pytest

from src.shared.config.cities import CityConfig, CityConfigLoader
from src.shared.constants import CITY_CODES


class TestCityConfig:
    """Test suite for CityConfig model."""

    def test_city_config_validation(self) -> None:
        """Test that CityConfig validates fields correctly."""
        config = CityConfig(
            code="NYC",
            name="New York City",
            lat=40.7128,
            lon=-74.0060,
            timezone="America/New_York",
            cluster="NE",
            settlement_station="KNYC",
            nws_office="OKX",
            nws_grid_x=32,
            nws_grid_y=34,
        )

        assert config.code == "NYC"
        assert config.name == "New York City"
        assert config.lat == 40.7128
        assert config.lon == -74.0060

    def test_city_config_validates_latitude_range(self) -> None:
        """Test that latitude is validated to be in valid range."""
        with pytest.raises(ValueError):
            CityConfig(
                code="NYC",
                name="New York City",
                lat=100.0,  # Invalid
                lon=-74.0060,
                timezone="America/New_York",
                cluster="NE",
                settlement_station="KNYC",
                nws_office="OKX",
                nws_grid_x=32,
                nws_grid_y=34,
            )

    def test_city_config_validates_longitude_range(self) -> None:
        """Test that longitude is validated to be in valid range."""
        with pytest.raises(ValueError):
            CityConfig(
                code="NYC",
                name="New York City",
                lat=40.7128,
                lon=-200.0,  # Invalid
                timezone="America/New_York",
                cluster="NE",
                settlement_station="KNYC",
                nws_office="OKX",
                nws_grid_x=32,
                nws_grid_y=34,
            )


class TestCityConfigLoader:
    """Test suite for CityConfigLoader."""

    def test_loader_raises_if_file_not_found(self, tmp_path: Path) -> None:
        """Test that loader raises FileNotFoundError if config file missing."""
        loader = CityConfigLoader(config_path=tmp_path / "nonexistent.json")

        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_loader_validates_required_cities(self, tmp_path: Path) -> None:
        """Test that loader validates all required cities are present."""
        config_file = tmp_path / "cities.json"

        # Create config with only one city (missing others)
        config_data = {
            "NYC": {
                "code": "NYC",
                "name": "New York City",
                "lat": 40.7128,
                "lon": -74.0060,
                "timezone": "America/New_York",
                "cluster": "NE",
                "settlement_station": "KNYC",
                "nws_office": "OKX",
                "nws_grid_x": 32,
                "nws_grid_y": 34,
            }
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        loader = CityConfigLoader(config_path=config_file)

        with pytest.raises(ValueError) as exc_info:
            loader.load()

        assert "Missing city configurations" in str(exc_info.value)

    def test_loader_loads_valid_config(self, tmp_path: Path) -> None:
        """Test that loader successfully loads valid configuration."""
        config_file = tmp_path / "cities.json"

        # Create complete config for all cities
        config_data = {
            code: {
                "code": code,
                "name": f"City {code}",
                "lat": 40.0,
                "lon": -74.0,
                "timezone": "America/New_York",
                "cluster": "NE",
                "settlement_station": f"K{code}",
                "nws_office": "OKX",
                "nws_grid_x": 32,
                "nws_grid_y": 34,
            }
            for code in CITY_CODES
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        loader = CityConfigLoader(config_path=config_file)
        cities = loader.load()

        assert len(cities) == len(CITY_CODES)
        assert all(code in cities for code in CITY_CODES)
        assert all(isinstance(city, CityConfig) for city in cities.values())

    def test_get_city_returns_config(self, tmp_path: Path) -> None:
        """Test that get_city returns the correct city configuration."""
        config_file = tmp_path / "cities.json"

        config_data = {
            code: {
                "code": code,
                "name": f"City {code}",
                "lat": 40.0,
                "lon": -74.0,
                "timezone": "America/New_York",
                "cluster": "NE",
                "settlement_station": f"K{code}",
                "nws_office": "OKX",
                "nws_grid_x": 32,
                "nws_grid_y": 34,
            }
            for code in CITY_CODES
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        loader = CityConfigLoader(config_path=config_file)
        city = loader.get_city("NYC")

        assert city.code == "NYC"
        assert city.name == "City NYC"

    def test_get_city_raises_for_invalid_code(self, tmp_path: Path) -> None:
        """Test that get_city raises KeyError for invalid city code."""
        config_file = tmp_path / "cities.json"

        config_data = {
            code: {
                "code": code,
                "name": f"City {code}",
                "lat": 40.0,
                "lon": -74.0,
                "timezone": "America/New_York",
                "cluster": "NE",
                "settlement_station": f"K{code}",
                "nws_office": "OKX",
                "nws_grid_x": 32,
                "nws_grid_y": 34,
            }
            for code in CITY_CODES
        }

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        loader = CityConfigLoader(config_path=config_file)

        with pytest.raises(KeyError):
            loader.get_city("INVALID")
