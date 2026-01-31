"""Market snapshot repository.

Provides data access for market snapshots with Pydantic model conversion.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from src.shared.config.logging import get_logger
from src.shared.db.connection import DatabaseManager
from src.shared.db.models import MarketSnapshot
from src.shared.db.repositories.base import BaseRepository

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models for Repository Returns
# ============================================================================


class MarketSnapshotModel(BaseModel):
    """Pydantic model for market snapshot data.

    Returned by MarketRepository methods for type-safe access.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    city_code: str
    event_ticker: str | None = None
    captured_at: datetime
    yes_bid: int | None = None
    yes_ask: int | None = None
    no_bid: int | None = None
    no_ask: int | None = None
    last_price: int | None = None
    volume: int = 0
    open_interest: int = 0
    status: str = "unknown"
    strike_price: float | None = None
    close_time: datetime | None = None
    expiration_time: datetime | None = None
    raw_payload: dict[str, Any] | None = None
    created_at: datetime

    @property
    def spread_cents(self) -> int | None:
        """Calculate bid-ask spread."""
        if self.yes_bid is not None and self.yes_ask is not None:
            return self.yes_ask - self.yes_bid
        return None

    @property
    def mid_price(self) -> float | None:
        """Calculate mid price."""
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2.0
        return None


class MarketSnapshotCreate(BaseModel):
    """Model for creating a new market snapshot."""

    ticker: str = Field(..., max_length=100)
    city_code: str = Field(..., max_length=3)
    event_ticker: str | None = None
    yes_bid: int | None = None
    yes_ask: int | None = None
    no_bid: int | None = None
    no_ask: int | None = None
    last_price: int | None = None
    volume: int = 0
    open_interest: int = 0
    status: str = "open"
    strike_price: float | None = None
    close_time: datetime | None = None
    expiration_time: datetime | None = None
    raw_payload: dict[str, Any] | None = None


# ============================================================================
# Repository Implementation
# ============================================================================


class MarketRepository(BaseRepository[MarketSnapshot]):
    """Repository for market snapshot data access.

    Provides methods for saving and retrieving market snapshots
    with automatic Pydantic model conversion.

    Example:
        >>> repo = MarketRepository(db_manager)
        >>> snapshot = repo.save_snapshot(MarketSnapshotCreate(
        ...     ticker="HIGHNYC-26JAN26",
        ...     city_code="NYC",
        ...     yes_bid=45,
        ...     yes_ask=48,
        ... ))
        >>> active = repo.get_active_markets("NYC")
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize market repository.

        Args:
            db_manager: Database manager instance
        """
        super().__init__(db_manager, MarketSnapshot)

    def save_snapshot(self, data: MarketSnapshotCreate) -> MarketSnapshotModel:
        """Save a new market snapshot.

        Args:
            data: Market snapshot data to save

        Returns:
            Saved market snapshot as Pydantic model
        """
        snapshot = MarketSnapshot(
            ticker=data.ticker,
            city_code=data.city_code,
            event_ticker=data.event_ticker,
            captured_at=self._utc_now(),
            yes_bid=data.yes_bid,
            yes_ask=data.yes_ask,
            no_bid=data.no_bid,
            no_ask=data.no_ask,
            last_price=data.last_price,
            volume=data.volume,
            open_interest=data.open_interest,
            status=data.status,
            strike_price=data.strike_price,
            close_time=data.close_time,
            expiration_time=data.expiration_time,
            raw_payload=data.raw_payload,
        )

        saved = self.save(snapshot)

        logger.info(
            "market_snapshot_saved",
            ticker=data.ticker,
            city_code=data.city_code,
            id=saved.id,
        )

        return MarketSnapshotModel.model_validate(saved)

    def get_latest(self, ticker: str) -> MarketSnapshotModel | None:
        """Get the most recent market snapshot for a ticker.

        Args:
            ticker: Market ticker

        Returns:
            Latest market snapshot or None if not found
        """
        with self._db.session() as session:
            stmt = (
                select(MarketSnapshot)
                .where(MarketSnapshot.ticker == ticker)
                .order_by(desc(MarketSnapshot.captured_at))
                .limit(1)
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                session.expunge(result)
                return MarketSnapshotModel.model_validate(result)
            return None

    def get_active_markets(self, city_code: str) -> list[MarketSnapshotModel]:
        """Get the latest snapshot for all active markets in a city.

        Args:
            city_code: 3-letter city code

        Returns:
            List of latest market snapshots with status='open'
        """
        from sqlalchemy import func

        with self._db.session() as session:
            # Subquery to get max captured_at per ticker for this city
            subq = (
                select(
                    MarketSnapshot.ticker,
                    func.max(MarketSnapshot.captured_at).label("max_captured"),
                )
                .where(MarketSnapshot.city_code == city_code)
                .group_by(MarketSnapshot.ticker)
                .subquery()
            )

            # Join to get full records, filter to open status
            stmt = (
                select(MarketSnapshot)
                .join(
                    subq,
                    (MarketSnapshot.ticker == subq.c.ticker)
                    & (MarketSnapshot.captured_at == subq.c.max_captured),
                )
                .where(MarketSnapshot.status == "open")
            )

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [MarketSnapshotModel.model_validate(r) for r in results]

    def get_markets_by_status(
        self, status: str, city_code: str | None = None
    ) -> list[MarketSnapshotModel]:
        """Get latest snapshots for markets with given status.

        Args:
            status: Market status (open, closed, settled)
            city_code: Optional city filter

        Returns:
            List of latest market snapshots
        """
        from sqlalchemy import func

        with self._db.session() as session:
            # Base subquery for latest per ticker
            subq_query = select(
                MarketSnapshot.ticker,
                func.max(MarketSnapshot.captured_at).label("max_captured"),
            )

            if city_code:
                subq_query = subq_query.where(MarketSnapshot.city_code == city_code)

            subq = subq_query.group_by(MarketSnapshot.ticker).subquery()

            # Main query
            stmt = (
                select(MarketSnapshot)
                .join(
                    subq,
                    (MarketSnapshot.ticker == subq.c.ticker)
                    & (MarketSnapshot.captured_at == subq.c.max_captured),
                )
                .where(MarketSnapshot.status == status)
            )

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [MarketSnapshotModel.model_validate(r) for r in results]

    def get_history(
        self,
        ticker: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[MarketSnapshotModel]:
        """Get market snapshot history for a ticker.

        Args:
            ticker: Market ticker
            start_time: Optional start of time range
            end_time: Optional end of time range
            limit: Maximum records to return

        Returns:
            List of market snapshots, newest first
        """
        with self._db.session() as session:
            stmt = select(MarketSnapshot).where(MarketSnapshot.ticker == ticker)

            if start_time:
                stmt = stmt.where(MarketSnapshot.captured_at >= start_time)
            if end_time:
                stmt = stmt.where(MarketSnapshot.captured_at <= end_time)

            stmt = stmt.order_by(desc(MarketSnapshot.captured_at)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [MarketSnapshotModel.model_validate(r) for r in results]

    def get_by_strike_range(
        self,
        city_code: str,
        min_strike: float,
        max_strike: float,
        status: str = "open",
    ) -> list[MarketSnapshotModel]:
        """Get latest snapshots for markets within a strike price range.

        Args:
            city_code: 3-letter city code
            min_strike: Minimum strike price
            max_strike: Maximum strike price
            status: Market status filter

        Returns:
            List of market snapshots within strike range
        """
        from sqlalchemy import func

        with self._db.session() as session:
            subq = (
                select(
                    MarketSnapshot.ticker,
                    func.max(MarketSnapshot.captured_at).label("max_captured"),
                )
                .where(MarketSnapshot.city_code == city_code)
                .where(MarketSnapshot.strike_price >= min_strike)
                .where(MarketSnapshot.strike_price <= max_strike)
                .group_by(MarketSnapshot.ticker)
                .subquery()
            )

            stmt = (
                select(MarketSnapshot)
                .join(
                    subq,
                    (MarketSnapshot.ticker == subq.c.ticker)
                    & (MarketSnapshot.captured_at == subq.c.max_captured),
                )
                .where(MarketSnapshot.status == status)
                .order_by(MarketSnapshot.strike_price)
            )

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [MarketSnapshotModel.model_validate(r) for r in results]

    def delete_older_than(self, days: int = 30) -> int:
        """Delete market snapshots older than specified days.

        Args:
            days: Delete records older than this many days

        Returns:
            Number of records deleted
        """
        from datetime import timedelta

        from sqlalchemy import delete

        cutoff = self._utc_now() - timedelta(days=days)

        with self._db.session() as session:
            stmt = delete(MarketSnapshot).where(MarketSnapshot.captured_at < cutoff)
            result = session.execute(stmt)
            count = result.rowcount

            logger.info(
                "old_market_snapshots_deleted",
                days=days,
                count=count,
            )
            return count
