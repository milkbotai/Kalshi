"""Core constants for Milkbot trading system.

This module defines all constants used across the application including
city codes, market parameters, and system limits.
"""

from typing import Final

# City codes for the 10 target cities
CITY_CODES: Final[list[str]] = [
    "NYC",  # New York City
    "CHI",  # Chicago
    "LAX",  # Los Angeles
    "MIA",  # Miami
    "AUS",  # Austin
    "DEN",  # Denver
    "PHL",  # Philadelphia
    "BOS",  # Boston
    "SEA",  # Seattle
    "SFO",  # San Francisco
]

# Market parameters
MAX_POSITION_SIZE: Final[int] = 1000  # Maximum contracts per position
MIN_EDGE_BPS: Final[int] = 50  # Minimum edge in basis points (0.5%)
MAX_SPREAD_BPS: Final[int] = 200  # Maximum acceptable spread (2%)

# API rate limits
KALSHI_RATE_LIMIT_PER_SECOND: Final[int] = 10
NWS_RATE_LIMIT_PER_SECOND: Final[int] = 1

# Timeouts (seconds)
API_TIMEOUT_SECONDS: Final[int] = 30
DB_QUERY_TIMEOUT_SECONDS: Final[int] = 10

# Forecast parameters
FORECAST_HORIZON_HOURS: Final[int] = 168  # 7 days
FORECAST_UPDATE_INTERVAL_MINUTES: Final[int] = 60

# Database
MAX_DB_CONNECTIONS: Final[int] = 10
DB_CONNECTION_TIMEOUT_SECONDS: Final[int] = 5

# Logging
LOG_RETENTION_DAYS: Final[int] = 30
LOG_LEVEL_DEFAULT: Final[str] = "INFO"

# Public disclosure settings (per DEFINITIONS.md)
PUBLIC_TRADE_DELAY_MIN: Final[int] = 60  # 60-minute delay before trades are public
DASH_REFRESH_SEC: Final[int] = 5  # Dashboard refresh interval
WEATHER_CACHE_MIN: Final[int] = 5  # Weather data cache TTL
