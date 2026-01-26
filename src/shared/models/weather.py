"""Weather snapshot model for storing forecast and observation data.

Captures weather data from NWS and other sources for trading decisions.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.base import Base, TimestampMixin


class WeatherSnapshot(Base, TimestampMixin):
    """Weather data snapshot model.
    
    Stores forecast and observation data from NWS and other sources.
    Used as input for trading strategies.
    """

    __tablename__ = "weather_snapshots"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # City identifier
    city_code: Mapped[str] = mapped_column(
        String(3), nullable=False, index=True, doc="3-letter city code"
    )

    # Capture timestamp
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, doc="When data was captured"
    )

    # NWS forecast data (raw JSON)
    nws_forecast: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="NWS forecast periods JSON"
    )

    # NWS observation data (raw JSON)
    nws_observation: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="NWS latest observation JSON"
    )

    # Secondary forecast source (optional)
    secondary_forecast: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Secondary forecast provider JSON"
    )

    # Climate normals for baseline
    normals: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Climate normals (mean, std) JSON"
    )

    # Data quality flags
    data_quality_flags: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Data freshness and quality indicators"
    )

    # Source URLs for audit trail
    nws_forecast_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="NWS forecast API URL"
    )
    nws_observation_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="NWS observation API URL"
    )

    __table_args__ = ({"comment": "Weather forecast and observation snapshots"},)

    def __repr__(self) -> str:
        """String representation of WeatherSnapshot."""
        return f"<WeatherSnapshot(city={self.city_code}, captured_at={self.captured_at})>"

    @property
    def is_stale(self) -> bool:
        """Check if weather data is stale (>15 minutes old).
        
        Returns:
            True if data is stale
        """
        from src.shared.models.base import utcnow

        age_minutes = (utcnow() - self.captured_at).total_seconds() / 60
        return age_minutes > 15

    @property
    def has_forecast(self) -> bool:
        """Check if forecast data is available.
        
        Returns:
            True if NWS forecast data exists
        """
        return self.nws_forecast is not None and len(self.nws_forecast) > 0
