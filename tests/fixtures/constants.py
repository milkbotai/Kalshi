"""Test fixtures for constants and configuration.

Provides reusable test data for unit and integration tests.
"""

from typing import Any

import pytest

# Sample city data for testing
SAMPLE_CITY_DATA: dict[str, Any] = {
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
    },
    "CHI": {
        "code": "CHI",
        "name": "Chicago",
        "lat": 41.8781,
        "lon": -87.6298,
        "timezone": "America/Chicago",
        "cluster": "Midwest",
        "settlement_station": "KORD",
        "nws_office": "LOT",
        "nws_grid_x": 75,
        "nws_grid_y": 73,
    },
}

# Sample forecast data
SAMPLE_FORECAST_DATA: dict[str, Any] = {
    "temperature": 72.5,
    "dewpoint": 55.0,
    "wind_speed": 10.5,
    "wind_direction": 180,
    "sky_cover": 25,
    "probability_of_precipitation": 10,
}

# Sample market data
SAMPLE_MARKET_DATA: dict[str, Any] = {
    "ticker": "HIGHNYC-25JAN26",
    "yes_bid": 45,
    "yes_ask": 48,
    "no_bid": 52,
    "no_ask": 55,
    "volume": 1500,
    "open_interest": 5000,
}


@pytest.fixture
def sample_city_data() -> dict[str, Any]:
    """Provide sample city configuration data."""
    return SAMPLE_CITY_DATA.copy()


@pytest.fixture
def sample_forecast() -> dict[str, Any]:
    """Provide sample forecast data."""
    return SAMPLE_FORECAST_DATA.copy()


@pytest.fixture
def sample_market() -> dict[str, Any]:
    """Provide sample market data."""
    return SAMPLE_MARKET_DATA.copy()
