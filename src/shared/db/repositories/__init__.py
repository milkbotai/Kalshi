"""Repository pattern implementation for database access.

Provides type-safe data access layer that returns Pydantic models.
"""

from src.shared.db.repositories.base import BaseRepository
from src.shared.db.repositories.fill import FillRepository
from src.shared.db.repositories.market import MarketRepository
from src.shared.db.repositories.order import OrderRepository
from src.shared.db.repositories.position import PositionRepository
from src.shared.db.repositories.signal import SignalRepository
from src.shared.db.repositories.weather import WeatherRepository

__all__ = [
    "BaseRepository",
    "WeatherRepository",
    "MarketRepository",
    "SignalRepository",
    "OrderRepository",
    "FillRepository",
    "PositionRepository",
]
