"""Fill repository.

Provides data access for trade executions (fills).
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from src.shared.config.logging import get_logger
from src.shared.db.connection import DatabaseManager
from src.shared.db.models import Fill
from src.shared.db.repositories.base import BaseRepository

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models for Repository Returns
# ============================================================================


class FillModel(BaseModel):
    """Pydantic model for fill data.

    Returned by FillRepository methods for type-safe access.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    kalshi_fill_id: str | None = None
    kalshi_order_id: str | None = None
    ticker: str
    city_code: str
    side: str
    action: str
    quantity: int
    price: float
    notional_value: float
    fees: float = 0.0
    realized_pnl: float | None = None
    trading_mode: str = "shadow"
    fill_time: datetime
    created_at: datetime


class FillCreate(BaseModel):
    """Model for creating a new fill."""

    order_id: int
    kalshi_fill_id: str | None = None
    kalshi_order_id: str | None = None
    ticker: str = Field(..., max_length=100)
    city_code: str = Field(..., max_length=3)
    side: str
    action: str
    quantity: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    fees: float = 0.0
    realized_pnl: float | None = None
    trading_mode: str = "shadow"
    fill_time: datetime | None = None


# ============================================================================
# Repository Implementation
# ============================================================================


class FillRepository(BaseRepository[Fill]):
    """Repository for fill (trade execution) data access.

    Provides methods for saving and retrieving fills.

    Example:
        >>> repo = FillRepository(db_manager)
        >>> fill = repo.save_fill(FillCreate(
        ...     order_id=123,
        ...     ticker="HIGHNYC-26JAN26",
        ...     city_code="NYC",
        ...     side="yes",
        ...     action="buy",
        ...     quantity=50,
        ...     price=45.0,
        ... ))
        >>> fills = repo.get_fills_for_order(123)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize fill repository.

        Args:
            db_manager: Database manager instance
        """
        super().__init__(db_manager, Fill)

    def save_fill(self, data: FillCreate) -> FillModel:
        """Save a new fill.

        Args:
            data: Fill data to save

        Returns:
            Saved fill as Pydantic model
        """
        fill_time = data.fill_time or self._utc_now()
        notional_value = data.price * data.quantity

        fill = Fill(
            order_id=data.order_id,
            kalshi_fill_id=data.kalshi_fill_id,
            kalshi_order_id=data.kalshi_order_id,
            ticker=data.ticker,
            city_code=data.city_code,
            side=data.side,
            action=data.action,
            quantity=data.quantity,
            price=data.price,
            notional_value=notional_value,
            fees=data.fees,
            realized_pnl=data.realized_pnl,
            trading_mode=data.trading_mode,
            fill_time=fill_time,
        )

        saved = self.save(fill)

        logger.info(
            "fill_saved",
            order_id=data.order_id,
            ticker=data.ticker,
            quantity=data.quantity,
            price=data.price,
            id=saved.id,
        )

        return FillModel.model_validate(saved)

    def get_fills_for_order(self, order_id: int) -> list[FillModel]:
        """Get all fills for an order.

        Args:
            order_id: Order ID

        Returns:
            List of fills for the order
        """
        with self._db.session() as session:
            stmt = (
                select(Fill)
                .where(Fill.order_id == order_id)
                .order_by(Fill.fill_time)
            )

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [FillModel.model_validate(r) for r in results]

    def get_fills_for_ticker(
        self,
        ticker: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[FillModel]:
        """Get fills for a specific ticker.

        Args:
            ticker: Market ticker
            start_time: Optional start time
            end_time: Optional end time
            limit: Maximum records to return

        Returns:
            List of fills, newest first
        """
        with self._db.session() as session:
            stmt = select(Fill).where(Fill.ticker == ticker)

            if start_time:
                stmt = stmt.where(Fill.fill_time >= start_time)
            if end_time:
                stmt = stmt.where(Fill.fill_time <= end_time)

            stmt = stmt.order_by(desc(Fill.fill_time)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [FillModel.model_validate(r) for r in results]

    def get_recent_fills(
        self,
        city_code: str | None = None,
        trading_mode: str | None = None,
        limit: int = 100,
    ) -> list[FillModel]:
        """Get recent fills with optional filters.

        Args:
            city_code: Optional city filter
            trading_mode: Optional trading mode filter
            limit: Maximum records to return

        Returns:
            List of fills, newest first
        """
        with self._db.session() as session:
            stmt = select(Fill)

            if city_code:
                stmt = stmt.where(Fill.city_code == city_code)
            if trading_mode:
                stmt = stmt.where(Fill.trading_mode == trading_mode)

            stmt = stmt.order_by(desc(Fill.fill_time)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [FillModel.model_validate(r) for r in results]

    def get_public_fills(
        self,
        city_code: str | None = None,
        delay_minutes: int = 60,
        limit: int = 100,
    ) -> list[FillModel]:
        """Get public fills with time delay.

        Only returns fills older than delay_minutes for public disclosure.

        Args:
            city_code: Optional city filter
            delay_minutes: Delay before fills are public (default 60)
            limit: Maximum records to return

        Returns:
            List of public fills, newest first
        """
        from datetime import timedelta

        cutoff = self._utc_now() - timedelta(minutes=delay_minutes)

        with self._db.session() as session:
            stmt = select(Fill).where(Fill.fill_time < cutoff)

            if city_code:
                stmt = stmt.where(Fill.city_code == city_code)

            stmt = stmt.order_by(desc(Fill.fill_time)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [FillModel.model_validate(r) for r in results]

    def get_fills_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        city_code: str | None = None,
    ) -> list[FillModel]:
        """Get fills within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            city_code: Optional city filter

        Returns:
            List of fills
        """
        with self._db.session() as session:
            stmt = (
                select(Fill)
                .where(Fill.fill_time >= start_date)
                .where(Fill.fill_time <= end_date)
            )

            if city_code:
                stmt = stmt.where(Fill.city_code == city_code)

            stmt = stmt.order_by(Fill.fill_time)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [FillModel.model_validate(r) for r in results]

    def get_fill_stats(
        self,
        city_code: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get fill statistics.

        Args:
            city_code: Optional city filter
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Dictionary with fill statistics
        """
        from sqlalchemy import func

        with self._db.session() as session:
            stmt = select(
                func.count(Fill.id).label("total_fills"),
                func.sum(Fill.quantity).label("total_quantity"),
                func.sum(Fill.notional_value).label("total_notional"),
                func.sum(Fill.fees).label("total_fees"),
                func.sum(Fill.realized_pnl).label("total_pnl"),
                func.avg(Fill.price).label("avg_price"),
            )

            if city_code:
                stmt = stmt.where(Fill.city_code == city_code)
            if start_time:
                stmt = stmt.where(Fill.fill_time >= start_time)
            if end_time:
                stmt = stmt.where(Fill.fill_time <= end_time)

            row = session.execute(stmt).one()

            return {
                "total_fills": row[0] or 0,
                "total_quantity": row[1] or 0,
                "total_notional": float(row[2]) if row[2] else 0.0,
                "total_fees": float(row[3]) if row[3] else 0.0,
                "total_pnl": float(row[4]) if row[4] else 0.0,
                "avg_price": float(row[5]) if row[5] else 0.0,
            }

    def get_pnl_by_city(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, float]:
        """Get realized P&L grouped by city.

        Args:
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Dictionary mapping city codes to realized P&L
        """
        from sqlalchemy import func

        with self._db.session() as session:
            stmt = select(
                Fill.city_code,
                func.sum(Fill.realized_pnl).label("total_pnl"),
            )

            if start_time:
                stmt = stmt.where(Fill.fill_time >= start_time)
            if end_time:
                stmt = stmt.where(Fill.fill_time <= end_time)

            stmt = stmt.group_by(Fill.city_code)

            results = session.execute(stmt).all()

            return {row[0]: float(row[1]) if row[1] else 0.0 for row in results}

    def get_volume_by_city(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, int]:
        """Get total volume grouped by city.

        Args:
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Dictionary mapping city codes to total volume
        """
        from sqlalchemy import func

        with self._db.session() as session:
            stmt = select(
                Fill.city_code,
                func.sum(Fill.quantity).label("total_volume"),
            )

            if start_time:
                stmt = stmt.where(Fill.fill_time >= start_time)
            if end_time:
                stmt = stmt.where(Fill.fill_time <= end_time)

            stmt = stmt.group_by(Fill.city_code)

            results = session.execute(stmt).all()

            return {row[0]: int(row[1]) if row[1] else 0 for row in results}

    def delete_older_than(self, days: int = 365) -> int:
        """Delete fills older than specified days.

        Args:
            days: Delete records older than this many days

        Returns:
            Number of records deleted
        """
        from datetime import timedelta

        from sqlalchemy import delete

        cutoff = self._utc_now() - timedelta(days=days)

        with self._db.session() as session:
            stmt = delete(Fill).where(Fill.fill_time < cutoff)
            result = session.execute(stmt)
            count = result.rowcount

            logger.info("old_fills_deleted", days=days, count=count)
            return count
