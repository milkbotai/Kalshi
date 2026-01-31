"""Position repository.

Provides data access for trading positions with cost basis tracking.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from src.shared.config.logging import get_logger
from src.shared.db.connection import DatabaseManager
from src.shared.db.models import Position
from src.shared.db.repositories.base import BaseRepository

logger = get_logger(__name__)


# ============================================================================
# Pydantic Models for Repository Returns
# ============================================================================


class PositionModel(BaseModel):
    """Pydantic model for position data.

    Returned by PositionRepository methods for type-safe access.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    city_code: str
    side: str
    quantity: int = 0
    entry_price: float = 0.0
    total_cost: float = 0.0
    fees_paid: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    is_closed: bool = False
    trading_mode: str = "shadow"
    opened_at: datetime
    closed_at: datetime | None = None
    updated_at: datetime

    @property
    def average_entry_price(self) -> float | None:
        """Calculate average entry price."""
        if self.quantity != 0:
            return self.total_cost / abs(self.quantity)
        return None

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.side == "yes"

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.side == "no"


class PositionCreate(BaseModel):
    """Model for creating a new position."""

    ticker: str = Field(..., max_length=100)
    city_code: str = Field(..., max_length=3)
    side: str  # "yes" or "no"
    quantity: int = Field(..., ge=0)
    entry_price: float = Field(..., ge=0)
    fees_paid: float = 0.0
    trading_mode: str = "shadow"


class PositionUpdate(BaseModel):
    """Model for updating a position."""

    quantity: int | None = None
    total_cost: float | None = None
    fees_paid: float | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    is_closed: bool | None = None


# ============================================================================
# Repository Implementation
# ============================================================================


class PositionRepository(BaseRepository[Position]):
    """Repository for position data access.

    Provides methods for managing positions with automatic cost basis tracking.

    Example:
        >>> repo = PositionRepository(db_manager)
        >>> pos = repo.open_position(PositionCreate(
        ...     ticker="HIGHNYC-26JAN26",
        ...     city_code="NYC",
        ...     side="yes",
        ...     quantity=100,
        ...     entry_price=45.0,
        ... ))
        >>> repo.add_to_position(pos.id, 50, 46.0)
        >>> repo.close_position(pos.id, exit_price=55.0)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize position repository.

        Args:
            db_manager: Database manager instance
        """
        super().__init__(db_manager, Position)

    def open_position(self, data: PositionCreate) -> PositionModel:
        """Open a new position.

        Args:
            data: Position data

        Returns:
            Created position as Pydantic model
        """
        total_cost = data.quantity * data.entry_price

        position = Position(
            ticker=data.ticker,
            city_code=data.city_code,
            side=data.side,
            quantity=data.quantity,
            entry_price=data.entry_price,
            total_cost=total_cost,
            fees_paid=data.fees_paid,
            trading_mode=data.trading_mode,
        )

        saved = self.save(position)

        logger.info(
            "position_opened",
            ticker=data.ticker,
            side=data.side,
            quantity=data.quantity,
            entry_price=data.entry_price,
            id=saved.id,
        )

        return PositionModel.model_validate(saved)

    def get_or_create_position(
        self,
        ticker: str,
        city_code: str,
        side: str,
        trading_mode: str = "shadow",
    ) -> tuple[PositionModel, bool]:
        """Get existing position or create new one.

        Args:
            ticker: Market ticker
            city_code: City code
            side: Position side
            trading_mode: Trading mode

        Returns:
            Tuple of (position, created) where created is True if new
        """
        existing = self.get_open_position(ticker, city_code, trading_mode)
        if existing:
            return existing, False

        # Create new position with zero quantity
        position = Position(
            ticker=ticker,
            city_code=city_code,
            side=side,
            quantity=0,
            entry_price=0.0,
            total_cost=0.0,
            trading_mode=trading_mode,
        )

        try:
            saved = self.save(position)
            return PositionModel.model_validate(saved), True
        except IntegrityError:
            # Race condition - position was created
            existing = self.get_open_position(ticker, city_code, trading_mode)
            if existing:
                return existing, False
            raise

    def get_open_position(
        self,
        ticker: str,
        city_code: str,
        trading_mode: str = "shadow",
    ) -> PositionModel | None:
        """Get open position for a ticker.

        Args:
            ticker: Market ticker
            city_code: City code
            trading_mode: Trading mode

        Returns:
            Open position or None if not found
        """
        with self._db.session() as session:
            stmt = (
                select(Position)
                .where(Position.ticker == ticker)
                .where(Position.city_code == city_code)
                .where(Position.trading_mode == trading_mode)
                .where(Position.is_closed == False)  # noqa: E712
            )

            result = session.execute(stmt).scalar_one_or_none()

            if result:
                session.expunge(result)
                return PositionModel.model_validate(result)
            return None

    def get_all_open_positions(
        self,
        city_code: str | None = None,
        trading_mode: str | None = None,
    ) -> list[PositionModel]:
        """Get all open positions.

        Args:
            city_code: Optional city filter
            trading_mode: Optional trading mode filter

        Returns:
            List of open positions
        """
        with self._db.session() as session:
            stmt = select(Position).where(Position.is_closed == False)  # noqa: E712

            if city_code:
                stmt = stmt.where(Position.city_code == city_code)
            if trading_mode:
                stmt = stmt.where(Position.trading_mode == trading_mode)

            stmt = stmt.order_by(desc(Position.opened_at))

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            return [PositionModel.model_validate(r) for r in results]

    def add_to_position(
        self,
        position_id: int,
        quantity: int,
        price: float,
        fees: float = 0.0,
    ) -> PositionModel | None:
        """Add to an existing position.

        Updates quantity and recalculates average entry price.

        Args:
            position_id: Position ID
            quantity: Quantity to add
            price: Price of this addition
            fees: Fees for this transaction

        Returns:
            Updated position or None if not found
        """
        position = self.get_by_id(position_id)
        if not position:
            return None

        # Calculate new totals
        new_quantity = position.quantity + quantity
        new_cost = position.total_cost + (quantity * price)
        new_fees = position.fees_paid + fees
        new_entry_price = new_cost / new_quantity if new_quantity > 0 else 0.0

        with self._db.session() as session:
            from sqlalchemy import update

            stmt = (
                update(Position)
                .where(Position.id == position_id)
                .values(
                    quantity=new_quantity,
                    total_cost=new_cost,
                    entry_price=new_entry_price,
                    fees_paid=new_fees,
                    updated_at=self._utc_now(),
                )
            )
            session.execute(stmt)

        logger.info(
            "position_increased",
            position_id=position_id,
            added_quantity=quantity,
            new_quantity=new_quantity,
            new_entry_price=new_entry_price,
        )

        return self._get_position_model(position_id)

    def reduce_position(
        self,
        position_id: int,
        quantity: int,
        exit_price: float,
        fees: float = 0.0,
    ) -> tuple[PositionModel | None, float]:
        """Reduce position and calculate realized P&L.

        Args:
            position_id: Position ID
            quantity: Quantity to close
            exit_price: Exit price
            fees: Fees for this transaction

        Returns:
            Tuple of (updated position, realized P&L)
        """
        position = self.get_by_id(position_id)
        if not position:
            return None, 0.0

        # Calculate P&L for this reduction
        avg_entry = position.total_cost / position.quantity if position.quantity > 0 else 0.0

        if position.side == "yes":
            # Long position: profit when exit > entry
            pnl = (exit_price - avg_entry) * quantity
        else:
            # Short position: profit when entry > exit
            pnl = (avg_entry - exit_price) * quantity

        pnl -= fees

        # Update position
        new_quantity = position.quantity - quantity
        # Proportionally reduce cost basis
        cost_reduction = (position.total_cost / position.quantity) * quantity if position.quantity > 0 else 0
        new_cost = position.total_cost - cost_reduction
        new_fees = position.fees_paid + fees
        new_realized_pnl = position.realized_pnl + pnl

        is_closed = new_quantity <= 0

        with self._db.session() as session:
            from sqlalchemy import update

            values: dict[str, Any] = {
                "quantity": max(0, new_quantity),
                "total_cost": max(0, new_cost),
                "fees_paid": new_fees,
                "realized_pnl": new_realized_pnl,
                "updated_at": self._utc_now(),
            }

            if is_closed:
                values["is_closed"] = True
                values["closed_at"] = self._utc_now()

            stmt = update(Position).where(Position.id == position_id).values(**values)
            session.execute(stmt)

        logger.info(
            "position_reduced",
            position_id=position_id,
            reduced_quantity=quantity,
            exit_price=exit_price,
            realized_pnl=pnl,
            is_closed=is_closed,
        )

        return self._get_position_model(position_id), pnl

    def close_position(
        self,
        position_id: int,
        exit_price: float,
        fees: float = 0.0,
    ) -> tuple[PositionModel | None, float]:
        """Close entire position.

        Args:
            position_id: Position ID
            exit_price: Exit price
            fees: Fees for closing

        Returns:
            Tuple of (closed position, realized P&L)
        """
        position = self.get_by_id(position_id)
        if not position or position.is_closed:
            return None, 0.0

        return self.reduce_position(
            position_id=position_id,
            quantity=position.quantity,
            exit_price=exit_price,
            fees=fees,
        )

    def update_unrealized_pnl(
        self,
        position_id: int,
        current_price: float,
    ) -> PositionModel | None:
        """Update unrealized P&L based on current market price.

        Args:
            position_id: Position ID
            current_price: Current market price

        Returns:
            Updated position or None if not found
        """
        position = self.get_by_id(position_id)
        if not position or position.is_closed:
            return None

        avg_entry = position.total_cost / position.quantity if position.quantity > 0 else 0.0

        if position.side == "yes":
            unrealized_pnl = (current_price - avg_entry) * position.quantity
        else:
            unrealized_pnl = (avg_entry - current_price) * position.quantity

        with self._db.session() as session:
            from sqlalchemy import update

            stmt = (
                update(Position)
                .where(Position.id == position_id)
                .values(
                    unrealized_pnl=unrealized_pnl,
                    updated_at=self._utc_now(),
                )
            )
            session.execute(stmt)

        return self._get_position_model(position_id)

    def get_position_summary(
        self,
        city_code: str | None = None,
        trading_mode: str | None = None,
    ) -> dict[str, Any]:
        """Get summary of all positions.

        Args:
            city_code: Optional city filter
            trading_mode: Optional trading mode filter

        Returns:
            Dictionary with position summary statistics
        """
        from sqlalchemy import func

        with self._db.session() as session:
            # Open positions stats
            open_stmt = select(
                func.count(Position.id).label("count"),
                func.sum(Position.quantity).label("total_quantity"),
                func.sum(Position.total_cost).label("total_cost"),
                func.sum(Position.unrealized_pnl).label("unrealized_pnl"),
            ).where(Position.is_closed == False)  # noqa: E712

            if city_code:
                open_stmt = open_stmt.where(Position.city_code == city_code)
            if trading_mode:
                open_stmt = open_stmt.where(Position.trading_mode == trading_mode)

            open_row = session.execute(open_stmt).one()

            # Closed positions stats
            closed_stmt = select(
                func.count(Position.id).label("count"),
                func.sum(Position.realized_pnl).label("realized_pnl"),
                func.sum(Position.fees_paid).label("total_fees"),
            ).where(Position.is_closed == True)  # noqa: E712

            if city_code:
                closed_stmt = closed_stmt.where(Position.city_code == city_code)
            if trading_mode:
                closed_stmt = closed_stmt.where(Position.trading_mode == trading_mode)

            closed_row = session.execute(closed_stmt).one()

            return {
                "open_positions": open_row[0] or 0,
                "open_quantity": open_row[1] or 0,
                "open_cost": float(open_row[2]) if open_row[2] else 0.0,
                "unrealized_pnl": float(open_row[3]) if open_row[3] else 0.0,
                "closed_positions": closed_row[0] or 0,
                "realized_pnl": float(closed_row[1]) if closed_row[1] else 0.0,
                "total_fees": float(closed_row[2]) if closed_row[2] else 0.0,
            }

    def get_positions_by_city(
        self,
        include_closed: bool = False,
    ) -> dict[str, list[PositionModel]]:
        """Get positions grouped by city.

        Args:
            include_closed: Whether to include closed positions

        Returns:
            Dictionary mapping city codes to their positions
        """
        with self._db.session() as session:
            stmt = select(Position)

            if not include_closed:
                stmt = stmt.where(Position.is_closed == False)  # noqa: E712

            stmt = stmt.order_by(Position.city_code, desc(Position.opened_at))

            results = list(session.execute(stmt).scalars().all())

            for r in results:
                session.expunge(r)

            # Group by city
            by_city: dict[str, list[PositionModel]] = {}
            for r in results:
                city = r.city_code
                if city not in by_city:
                    by_city[city] = []
                by_city[city].append(PositionModel.model_validate(r))

            return by_city

    def get_pnl_by_city(self, include_unrealized: bool = True) -> dict[str, float]:
        """Get total P&L grouped by city.

        Args:
            include_unrealized: Whether to include unrealized P&L

        Returns:
            Dictionary mapping city codes to total P&L
        """
        from sqlalchemy import func

        with self._db.session() as session:
            if include_unrealized:
                pnl_col = Position.realized_pnl + Position.unrealized_pnl
            else:
                pnl_col = Position.realized_pnl

            stmt = select(
                Position.city_code,
                func.sum(pnl_col).label("total_pnl"),
            ).group_by(Position.city_code)

            results = session.execute(stmt).all()

            return {row[0]: float(row[1]) if row[1] else 0.0 for row in results}

    def _get_position_model(self, position_id: int) -> PositionModel | None:
        """Get position by ID as Pydantic model.

        Args:
            position_id: Position ID

        Returns:
            Position model or None
        """
        position = self.get_by_id(position_id)
        if position:
            return PositionModel.model_validate(position)
        return None
