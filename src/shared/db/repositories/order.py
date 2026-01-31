"""Order repository with idempotency support.

Provides data access for orders with intent-key based idempotency.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from src.shared.config.logging import get_logger
from src.shared.db.connection import DatabaseManager
from src.shared.db.models import Order, OrderStatus
from src.shared.db.repositories.base import BaseRepository

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models for Repository Returns
# ============================================================================


class OrderModel(BaseModel):
    """Pydantic model for order data.

    Returned by OrderRepository methods for type-safe access.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    intent_key: str
    ticker: str
    city_code: str
    market_id: int | None = None
    event_date: str | None = None
    signal_id: int | None = None
    kalshi_order_id: str | None = None
    client_order_id: str | None = None
    side: str
    action: str
    quantity: int
    limit_price: float
    status: str
    filled_quantity: int = 0
    remaining_quantity: int
    average_fill_price: float | None = None
    signal_p_yes: float | None = None
    signal_edge: float | None = None
    trading_mode: str = "shadow"
    status_message: str | None = None
    created_at: datetime
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    cancelled_at: datetime | None = None
    updated_at: datetime

    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == OrderStatus.FILLED.value

    @property
    def is_open(self) -> bool:
        """Check if order is still open (can be filled)."""
        return self.status in [
            OrderStatus.PENDING.value,
            OrderStatus.SUBMITTED.value,
            OrderStatus.RESTING.value,
            OrderStatus.PARTIALLY_FILLED.value,
        ]


class OrderCreate(BaseModel):
    """Model for creating a new order."""

    intent_key: str = Field(..., max_length=64)
    ticker: str = Field(..., max_length=100)
    city_code: str = Field(..., max_length=3)
    market_id: int | None = None
    event_date: str | None = None
    signal_id: int | None = None
    side: str  # "yes" or "no"
    action: str = "buy"  # "buy" or "sell"
    quantity: int = Field(..., gt=0)
    limit_price: float = Field(..., ge=0)
    signal_p_yes: float | None = None
    signal_edge: float | None = None
    trading_mode: str = "shadow"


class OrderUpdate(BaseModel):
    """Model for updating an order."""

    status: str | None = None
    kalshi_order_id: str | None = None
    filled_quantity: int | None = None
    average_fill_price: float | None = None
    status_message: str | None = None


# ============================================================================
# Repository Implementation
# ============================================================================


class OrderRepository(BaseRepository[Order]):
    """Repository for order data access with idempotency.

    Uses intent_key for idempotent order creation - if an order with
    the same intent_key already exists, returns the existing order.

    Example:
        >>> repo = OrderRepository(db_manager)
        >>> order, created = repo.create_order_idempotent(OrderCreate(
        ...     intent_key="NYC-12345-2024-01-26-BUY",
        ...     ticker="HIGHNYC-26JAN26",
        ...     city_code="NYC",
        ...     side="yes",
        ...     quantity=100,
        ...     limit_price=45.0,
        ... ))
        >>> if created:
        ...     print("New order created")
        >>> else:
        ...     print("Existing order returned")
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize order repository.

        Args:
            db_manager: Database manager instance
        """
        super().__init__(db_manager, Order)

    def create_order_idempotent(
        self, data: OrderCreate
    ) -> tuple[OrderModel, bool]:
        """Create order with idempotency check.

        If an order with the same intent_key exists, returns the existing
        order without creating a duplicate.

        Args:
            data: Order data to create

        Returns:
            Tuple of (order, created) where created is True if new order
        """
        # First check if order already exists
        existing = self.get_by_intent_key(data.intent_key)
        if existing:
            logger.info(
                "order_already_exists",
                intent_key=data.intent_key,
                order_id=existing.id,
            )
            return existing, False

        # Create new order
        order = Order(
            intent_key=data.intent_key,
            ticker=data.ticker,
            city_code=data.city_code,
            market_id=data.market_id,
            event_date=data.event_date,
            signal_id=data.signal_id,
            side=data.side,
            action=data.action,
            quantity=data.quantity,
            limit_price=data.limit_price,
            status=OrderStatus.PENDING.value,
            remaining_quantity=data.quantity,
            signal_p_yes=data.signal_p_yes,
            signal_edge=data.signal_edge,
            trading_mode=data.trading_mode,
        )

        try:
            saved = self.save(order)

            logger.info(
                "order_created",
                intent_key=data.intent_key,
                ticker=data.ticker,
                id=saved.id,
            )

            return OrderModel.model_validate(saved), True

        except IntegrityError:
            # Race condition - order was created between check and insert
            existing = self.get_by_intent_key(data.intent_key)
            if existing:
                logger.info(
                    "order_race_condition_existing_returned",
                    intent_key=data.intent_key,
                )
                return existing, False
            raise

    def get_by_intent_key(self, intent_key: str) -> OrderModel | None:
        """Get order by intent key.

        Args:
            intent_key: Unique intent key

        Returns:
            Order if found, None otherwise
        """
        with self._db.session() as session:
            stmt = select(Order).where(Order.intent_key == intent_key)
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                session.expunge(result)
                return OrderModel.model_validate(result)
            return None

    def get_by_kalshi_id(self, kalshi_order_id: str) -> OrderModel | None:
        """Get order by Kalshi order ID.

        Args:
            kalshi_order_id: Kalshi's order ID

        Returns:
            Order if found, None otherwise
        """
        with self._db.session() as session:
            stmt = select(Order).where(Order.kalshi_order_id == kalshi_order_id)
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                session.expunge(result)
                return OrderModel.model_validate(result)
            return None

    def update_status(
        self,
        intent_key: str,
        new_status: str,
        kalshi_order_id: str | None = None,
        status_message: str | None = None,
    ) -> OrderModel | None:
        """Update order status by intent key.

        Args:
            intent_key: Intent key of order to update
            new_status: New status value
            kalshi_order_id: Optional Kalshi order ID to set
            status_message: Optional status message

        Returns:
            Updated order or None if not found
        """
        from sqlalchemy import update

        now = self._utc_now()

        with self._db.session() as session:
            # Build update values
            values: dict[str, Any] = {
                "status": new_status,
                "updated_at": now,
            }

            if kalshi_order_id:
                values["kalshi_order_id"] = kalshi_order_id

            if status_message:
                values["status_message"] = status_message

            # Set timestamp based on status
            if new_status == OrderStatus.SUBMITTED.value:
                values["submitted_at"] = now
            elif new_status == OrderStatus.FILLED.value:
                values["filled_at"] = now
            elif new_status in [OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value]:
                values["cancelled_at"] = now

            stmt = (
                update(Order)
                .where(Order.intent_key == intent_key)
                .values(**values)
            )
            session.execute(stmt)
            session.commit()

        # Return updated order
        return self.get_by_intent_key(intent_key)

    def record_fill(
        self,
        intent_key: str,
        fill_quantity: int,
        fill_price: float,
    ) -> OrderModel | None:
        """Record a fill against an order.

        Updates filled quantity, average price, and status.

        Args:
            intent_key: Intent key of order
            fill_quantity: Quantity filled in this execution
            fill_price: Price of this fill

        Returns:
            Updated order or None if not found
        """
        order = self.get_by_intent_key(intent_key)
        if not order:
            return None

        # Calculate new totals
        prev_filled = order.filled_quantity
        new_filled = prev_filled + fill_quantity
        new_remaining = order.quantity - new_filled

        # Calculate weighted average price
        if order.average_fill_price and prev_filled > 0:
            total_value = (order.average_fill_price * prev_filled) + (fill_price * fill_quantity)
            new_avg_price = total_value / new_filled
        else:
            new_avg_price = fill_price

        # Determine new status
        if new_remaining <= 0:
            new_status = OrderStatus.FILLED.value
        elif new_filled > 0:
            new_status = OrderStatus.PARTIALLY_FILLED.value
        else:
            new_status = order.status

        with self._db.session() as session:
            from sqlalchemy import update

            now = self._utc_now()
            values: dict[str, Any] = {
                "filled_quantity": new_filled,
                "remaining_quantity": new_remaining,
                "average_fill_price": new_avg_price,
                "status": new_status,
                "updated_at": now,
            }

            if new_status == OrderStatus.FILLED.value:
                values["filled_at"] = now

            stmt = (
                update(Order)
                .where(Order.intent_key == intent_key)
                .values(**values)
            )
            session.execute(stmt)

        logger.info(
            "order_fill_recorded",
            intent_key=intent_key,
            fill_quantity=fill_quantity,
            total_filled=new_filled,
            status=new_status,
        )

        return self.get_by_intent_key(intent_key)

    def get_open_orders(
        self,
        city_code: str | None = None,
        trading_mode: str | None = None,
    ) -> list[OrderModel]:
        """Get all open (non-terminal) orders.

        Args:
            city_code: Optional city filter
            trading_mode: Optional trading mode filter

        Returns:
            List of open orders
        """
        open_statuses = [
            OrderStatus.PENDING.value,
            OrderStatus.SUBMITTED.value,
            OrderStatus.RESTING.value,
            OrderStatus.PARTIALLY_FILLED.value,
        ]

        with self._db.session() as session:
            stmt = select(Order).where(Order.status.in_(open_statuses))

            if city_code:
                stmt = stmt.where(Order.city_code == city_code)
            if trading_mode:
                stmt = stmt.where(Order.trading_mode == trading_mode)

            stmt = stmt.order_by(desc(Order.created_at))

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [OrderModel.model_validate(r) for r in results]

    def get_orders_by_status(
        self,
        status: str,
        city_code: str | None = None,
        limit: int = 100,
    ) -> list[OrderModel]:
        """Get orders by status.

        Args:
            status: Order status to filter by
            city_code: Optional city filter
            limit: Maximum records to return

        Returns:
            List of orders with given status
        """
        with self._db.session() as session:
            stmt = select(Order).where(Order.status == status)

            if city_code:
                stmt = stmt.where(Order.city_code == city_code)

            stmt = stmt.order_by(desc(Order.created_at)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [OrderModel.model_validate(r) for r in results]

    def get_orders_for_ticker(
        self,
        ticker: str,
        include_closed: bool = False,
        limit: int = 100,
    ) -> list[OrderModel]:
        """Get orders for a specific ticker.

        Args:
            ticker: Market ticker
            include_closed: Whether to include terminal orders
            limit: Maximum records to return

        Returns:
            List of orders, newest first
        """
        with self._db.session() as session:
            stmt = select(Order).where(Order.ticker == ticker)

            if not include_closed:
                open_statuses = [
                    OrderStatus.PENDING.value,
                    OrderStatus.SUBMITTED.value,
                    OrderStatus.RESTING.value,
                    OrderStatus.PARTIALLY_FILLED.value,
                ]
                stmt = stmt.where(Order.status.in_(open_statuses))

            stmt = stmt.order_by(desc(Order.created_at)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [OrderModel.model_validate(r) for r in results]

    def get_recent_orders(
        self,
        city_code: str | None = None,
        trading_mode: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[OrderModel]:
        """Get recent orders with optional filters.

        Args:
            city_code: Optional city filter
            trading_mode: Optional trading mode filter
            start_time: Optional start time
            end_time: Optional end time
            limit: Maximum records to return

        Returns:
            List of orders, newest first
        """
        with self._db.session() as session:
            stmt = select(Order)

            if city_code:
                stmt = stmt.where(Order.city_code == city_code)
            if trading_mode:
                stmt = stmt.where(Order.trading_mode == trading_mode)
            if start_time:
                stmt = stmt.where(Order.created_at >= start_time)
            if end_time:
                stmt = stmt.where(Order.created_at <= end_time)

            stmt = stmt.order_by(desc(Order.created_at)).limit(limit)

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [OrderModel.model_validate(r) for r in results]

    def cancel_order(self, intent_key: str, reason: str = "User cancelled") -> OrderModel | None:
        """Cancel an open order.

        Args:
            intent_key: Intent key of order to cancel
            reason: Cancellation reason

        Returns:
            Updated order or None if not found or already closed
        """
        order = self.get_by_intent_key(intent_key)
        if not order or not order.is_open:
            return None

        return self.update_status(
            intent_key=intent_key,
            new_status=OrderStatus.CANCELLED.value,
            status_message=reason,
        )

    def get_order_stats(
        self,
        city_code: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get order statistics.

        Args:
            city_code: Optional city filter
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Dictionary with order statistics
        """
        from sqlalchemy import func

        with self._db.session() as session:
            # Base query
            base_query = select(Order)

            if city_code:
                base_query = base_query.where(Order.city_code == city_code)
            if start_time:
                base_query = base_query.where(Order.created_at >= start_time)
            if end_time:
                base_query = base_query.where(Order.created_at <= end_time)

            # Count by status
            status_query = (
                select(Order.status, func.count(Order.id).label("count"))
                .where(True)  # Base filter placeholder
            )
            if city_code:
                status_query = status_query.where(Order.city_code == city_code)
            if start_time:
                status_query = status_query.where(Order.created_at >= start_time)
            if end_time:
                status_query = status_query.where(Order.created_at <= end_time)
            status_query = status_query.group_by(Order.status)

            status_results = session.execute(status_query).all()
            status_counts = {row[0]: row[1] for row in status_results}

            # Total volume
            volume_query = select(func.sum(Order.quantity))
            if city_code:
                volume_query = volume_query.where(Order.city_code == city_code)
            if start_time:
                volume_query = volume_query.where(Order.created_at >= start_time)
            if end_time:
                volume_query = volume_query.where(Order.created_at <= end_time)

            total_volume = session.execute(volume_query).scalar() or 0

            return {
                "total_orders": sum(status_counts.values()),
                "by_status": status_counts,
                "total_volume": total_volume,
                "fill_rate": (
                    status_counts.get(OrderStatus.FILLED.value, 0)
                    / max(sum(status_counts.values()), 1)
                ),
            }
