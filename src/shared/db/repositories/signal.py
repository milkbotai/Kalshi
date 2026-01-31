"""Signal repository.

Provides data access for trading signals with Pydantic model conversion.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from src.shared.config.logging import get_logger
from src.shared.db.connection import DatabaseManager
from src.shared.db.models import Signal
from src.shared.db.repositories.base import BaseRepository

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models for Repository Returns
# ============================================================================


class SignalModel(BaseModel):
    """Pydantic model for signal data.

    Returned by SignalRepository methods for type-safe access.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    city_code: str
    strategy_name: str
    side: str | None = None
    decision: str  # "BUY", "SELL", "HOLD"
    p_yes: float
    uncertainty: float = 0.0
    edge: float = 0.0
    confidence: float = 0.0
    max_price: float | None = None
    reason: str | None = None
    features: dict[str, Any] | None = None
    weather_snapshot_id: int | None = None
    market_snapshot_id: int | None = None
    trading_mode: str = "shadow"
    created_at: datetime


class SignalCreate(BaseModel):
    """Model for creating a new signal."""

    ticker: str = Field(..., max_length=100)
    city_code: str = Field(..., max_length=3)
    strategy_name: str = Field(..., max_length=100)
    side: str | None = None
    decision: str  # "BUY", "SELL", "HOLD"
    p_yes: float = Field(..., ge=0.0, le=1.0)
    uncertainty: float = 0.0
    edge: float = 0.0
    confidence: float = 0.0
    max_price: float | None = None
    reason: str | None = None
    features: dict[str, Any] | None = None
    weather_snapshot_id: int | None = None
    market_snapshot_id: int | None = None
    trading_mode: str = "shadow"


# ============================================================================
# Repository Implementation
# ============================================================================


class SignalRepository(BaseRepository[Signal]):
    """Repository for trading signal data access.

    Provides methods for saving and retrieving signals
    with automatic Pydantic model conversion.

    Example:
        >>> repo = SignalRepository(db_manager)
        >>> signal = repo.save_signal(SignalCreate(
        ...     ticker="HIGHNYC-26JAN26",
        ...     city_code="NYC",
        ...     strategy_name="daily_high_temp",
        ...     decision="BUY",
        ...     p_yes=0.65,
        ...     edge=5.0,
        ... ))
        >>> recent = repo.get_recent_signals("NYC", limit=10)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize signal repository.

        Args:
            db_manager: Database manager instance
        """
        super().__init__(db_manager, Signal)

    def save_signal(self, data: SignalCreate) -> SignalModel:
        """Save a new trading signal.

        Args:
            data: Signal data to save

        Returns:
            Saved signal as Pydantic model
        """
        signal = Signal(
            ticker=data.ticker,
            city_code=data.city_code,
            strategy_name=data.strategy_name,
            side=data.side,
            decision=data.decision,
            p_yes=data.p_yes,
            uncertainty=data.uncertainty,
            edge=data.edge,
            confidence=data.confidence,
            max_price=data.max_price,
            reason=data.reason,
            features=data.features,
            weather_snapshot_id=data.weather_snapshot_id,
            market_snapshot_id=data.market_snapshot_id,
            trading_mode=data.trading_mode,
        )

        saved = self.save(signal)

        logger.info(
            "signal_saved",
            ticker=data.ticker,
            city_code=data.city_code,
            decision=data.decision,
            id=saved.id,
        )

        return SignalModel.model_validate(saved)

    def get_recent_signals(
        self,
        city_code: str | None = None,
        strategy_name: str | None = None,
        decision: str | None = None,
        limit: int = 100,
    ) -> list[SignalModel]:
        """Get recent signals with optional filters.

        Args:
            city_code: Optional city filter
            strategy_name: Optional strategy filter
            decision: Optional decision filter (BUY, SELL, HOLD)
            limit: Maximum records to return

        Returns:
            List of signals, newest first
        """
        with self._db.session() as session:
            stmt = select(Signal)

            if city_code:
                stmt = stmt.where(Signal.city_code == city_code)
            if strategy_name:
                stmt = stmt.where(Signal.strategy_name == strategy_name)
            if decision:
                stmt = stmt.where(Signal.decision == decision)

            stmt = stmt.order_by(desc(Signal.created_at)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [SignalModel.model_validate(r) for r in results]

    def get_signals_for_ticker(
        self,
        ticker: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[SignalModel]:
        """Get signals for a specific ticker.

        Args:
            ticker: Market ticker
            start_time: Optional start time
            end_time: Optional end time
            limit: Maximum records to return

        Returns:
            List of signals, newest first
        """
        with self._db.session() as session:
            stmt = select(Signal).where(Signal.ticker == ticker)

            if start_time:
                stmt = stmt.where(Signal.created_at >= start_time)
            if end_time:
                stmt = stmt.where(Signal.created_at <= end_time)

            stmt = stmt.order_by(desc(Signal.created_at)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [SignalModel.model_validate(r) for r in results]

    def get_actionable_signals(
        self,
        city_code: str | None = None,
        min_edge: float = 0.0,
        limit: int = 100,
    ) -> list[SignalModel]:
        """Get signals with BUY or SELL decisions that meet edge threshold.

        Args:
            city_code: Optional city filter
            min_edge: Minimum edge required
            limit: Maximum records to return

        Returns:
            List of actionable signals, newest first
        """
        with self._db.session() as session:
            stmt = (
                select(Signal)
                .where(Signal.decision.in_(["BUY", "SELL"]))
                .where(Signal.edge >= min_edge)
            )

            if city_code:
                stmt = stmt.where(Signal.city_code == city_code)

            stmt = stmt.order_by(desc(Signal.created_at)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [SignalModel.model_validate(r) for r in results]

    def get_signals_by_strategy(
        self,
        strategy_name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[SignalModel]:
        """Get all signals for a strategy within time range.

        Args:
            strategy_name: Strategy name
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            List of signals
        """
        with self._db.session() as session:
            stmt = select(Signal).where(Signal.strategy_name == strategy_name)

            if start_time:
                stmt = stmt.where(Signal.created_at >= start_time)
            if end_time:
                stmt = stmt.where(Signal.created_at <= end_time)

            stmt = stmt.order_by(desc(Signal.created_at))

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [SignalModel.model_validate(r) for r in results]

    def count_by_decision(
        self,
        city_code: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, int]:
        """Count signals grouped by decision type.

        Args:
            city_code: Optional city filter
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Dictionary with counts per decision type
        """
        from sqlalchemy import func

        with self._db.session() as session:
            stmt = select(Signal.decision, func.count(Signal.id).label("count"))

            if city_code:
                stmt = stmt.where(Signal.city_code == city_code)
            if start_time:
                stmt = stmt.where(Signal.created_at >= start_time)
            if end_time:
                stmt = stmt.where(Signal.created_at <= end_time)

            stmt = stmt.group_by(Signal.decision)

            results = session.execute(stmt).all()

            return {row[0]: row[1] for row in results}

    def get_average_edge_by_strategy(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, float]:
        """Get average edge grouped by strategy.

        Args:
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Dictionary mapping strategy names to average edge
        """
        from sqlalchemy import func

        with self._db.session() as session:
            stmt = select(
                Signal.strategy_name,
                func.avg(Signal.edge).label("avg_edge"),
            )

            if start_time:
                stmt = stmt.where(Signal.created_at >= start_time)
            if end_time:
                stmt = stmt.where(Signal.created_at <= end_time)

            stmt = stmt.group_by(Signal.strategy_name)

            results = session.execute(stmt).all()

            return {row[0]: float(row[1]) if row[1] else 0.0 for row in results}

    def delete_older_than(self, days: int = 90) -> int:
        """Delete signals older than specified days.

        Args:
            days: Delete records older than this many days

        Returns:
            Number of records deleted
        """
        from datetime import timedelta

        from sqlalchemy import delete

        cutoff = self._utc_now() - timedelta(days=days)

        with self._db.session() as session:
            stmt = delete(Signal).where(Signal.created_at < cutoff)
            result = session.execute(stmt)
            count = result.rowcount

            logger.info("old_signals_deleted", days=days, count=count)
            return count
