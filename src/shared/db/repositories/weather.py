"""Weather snapshot repository.

Provides data access for weather snapshots with Pydantic model conversion.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from src.shared.config.logging import get_logger
from src.shared.db.connection import DatabaseManager
from src.shared.db.models import WeatherSnapshot
from src.shared.db.repositories.base import BaseRepository

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models for Repository Returns
# ============================================================================


class WeatherSnapshotModel(BaseModel):
    """Pydantic model for weather snapshot data.

    Returned by WeatherRepository methods for type-safe access.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    city_code: str
    captured_at: datetime
    forecast_high: int | None = None
    forecast_low: int | None = None
    current_temp: float | None = None
    precipitation_probability: float | None = None
    forecast_text: str | None = None
    source: str = "nws"
    is_stale: bool = False
    raw_forecast: dict[str, Any] | None = None
    raw_observation: dict[str, Any] | None = None
    created_at: datetime


class WeatherSnapshotCreate(BaseModel):
    """Model for creating a new weather snapshot."""

    city_code: str = Field(..., max_length=3)
    forecast_high: int | None = None
    forecast_low: int | None = None
    current_temp: float | None = None
    precipitation_probability: float | None = None
    forecast_text: str | None = None
    source: str = "nws"
    is_stale: bool = False
    raw_forecast: dict[str, Any] | None = None
    raw_observation: dict[str, Any] | None = None


# ============================================================================
# Repository Implementation
# ============================================================================


class WeatherRepository(BaseRepository[WeatherSnapshot]):
    """Repository for weather snapshot data access.

    Provides methods for saving and retrieving weather snapshots
    with automatic Pydantic model conversion.

    Example:
        >>> repo = WeatherRepository(db_manager)
        >>> snapshot = repo.save_snapshot(WeatherSnapshotCreate(
        ...     city_code="NYC",
        ...     forecast_high=75,
        ...     current_temp=72.5,
        ... ))
        >>> latest = repo.get_latest("NYC")
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize weather repository.

        Args:
            db_manager: Database manager instance
        """
        super().__init__(db_manager, WeatherSnapshot)

    def save_snapshot(self, data: WeatherSnapshotCreate) -> WeatherSnapshotModel:
        """Save a new weather snapshot.

        Args:
            data: Weather snapshot data to save

        Returns:
            Saved weather snapshot as Pydantic model
        """
        snapshot = WeatherSnapshot(
            city_code=data.city_code,
            captured_at=self._utc_now(),
            forecast_high=data.forecast_high,
            forecast_low=data.forecast_low,
            current_temp=data.current_temp,
            precipitation_probability=data.precipitation_probability,
            forecast_text=data.forecast_text,
            source=data.source,
            is_stale=data.is_stale,
            raw_forecast=data.raw_forecast,
            raw_observation=data.raw_observation,
        )

        saved = self.save(snapshot)

        logger.info(
            "weather_snapshot_saved",
            city_code=data.city_code,
            id=saved.id,
        )

        return WeatherSnapshotModel.model_validate(saved)

    def get_latest(self, city_code: str) -> WeatherSnapshotModel | None:
        """Get the most recent weather snapshot for a city.

        Args:
            city_code: 3-letter city code

        Returns:
            Latest weather snapshot or None if not found
        """
        with self._db.session() as session:
            stmt = (
                select(WeatherSnapshot)
                .where(WeatherSnapshot.city_code == city_code)
                .order_by(desc(WeatherSnapshot.captured_at))
                .limit(1)
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                session.expunge(result)
                return WeatherSnapshotModel.model_validate(result)
            return None

    def get_history(
        self,
        city_code: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[WeatherSnapshotModel]:
        """Get weather snapshot history for a city.

        Args:
            city_code: 3-letter city code
            start_time: Optional start of time range
            end_time: Optional end of time range
            limit: Maximum records to return

        Returns:
            List of weather snapshots, newest first
        """
        with self._db.session() as session:
            stmt = select(WeatherSnapshot).where(WeatherSnapshot.city_code == city_code)

            if start_time:
                stmt = stmt.where(WeatherSnapshot.captured_at >= start_time)
            if end_time:
                stmt = stmt.where(WeatherSnapshot.captured_at <= end_time)

            stmt = stmt.order_by(desc(WeatherSnapshot.captured_at)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [WeatherSnapshotModel.model_validate(r) for r in results]

    def get_latest_for_all_cities(self) -> dict[str, WeatherSnapshotModel]:
        """Get the latest weather snapshot for each city.

        Returns:
            Dictionary mapping city codes to their latest snapshots
        """
        # Get all unique city codes first
        with self._db.session() as session:
            # Use a subquery to get max captured_at per city
            from sqlalchemy import func

            subq = (
                select(
                    WeatherSnapshot.city_code,
                    func.max(WeatherSnapshot.captured_at).label("max_captured"),
                )
                .group_by(WeatherSnapshot.city_code)
                .subquery()
            )

            stmt = select(WeatherSnapshot).join(
                subq,
                (WeatherSnapshot.city_code == subq.c.city_code)
                & (WeatherSnapshot.captured_at == subq.c.max_captured),
            )

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return {r.city_code: WeatherSnapshotModel.model_validate(r) for r in results}

    def mark_stale(self, city_code: str) -> int:
        """Mark all snapshots for a city as stale.

        Args:
            city_code: 3-letter city code

        Returns:
            Number of records updated
        """
        from sqlalchemy import update

        with self._db.session() as session:
            stmt = (
                update(WeatherSnapshot)
                .where(WeatherSnapshot.city_code == city_code)
                .where(WeatherSnapshot.is_stale == False)  # noqa: E712
                .values(is_stale=True)
            )
            result = session.execute(stmt)
            count = result.rowcount

            logger.info("weather_snapshots_marked_stale", city_code=city_code, count=count)
            return count

    def delete_older_than(self, days: int = 30) -> int:
        """Delete weather snapshots older than specified days.

        Args:
            days: Delete records older than this many days

        Returns:
            Number of records deleted
        """
        from datetime import timedelta

        from sqlalchemy import delete

        cutoff = self._utc_now() - timedelta(days=days)

        with self._db.session() as session:
            stmt = delete(WeatherSnapshot).where(WeatherSnapshot.captured_at < cutoff)
            result = session.execute(stmt)
            count = result.rowcount

            logger.info(
                "old_weather_snapshots_deleted",
                days=days,
                count=count,
            )
            return count
