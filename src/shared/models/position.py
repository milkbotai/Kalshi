"""Position model for tracking open positions.

Represents current positions held in Kalshi markets.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.shared.models.market import Market


class Position(Base, TimestampMixin):
    """Trading position model.

    Tracks open positions in markets including quantity, entry price,
    and current P&L.
    """

    __tablename__ = "positions"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to market
    market_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to market",
    )

    # Position details
    ticker: Mapped[str] = mapped_column(String(50), nullable=False, index=True, doc="Market ticker")
    side: Mapped[str] = mapped_column(String(10), nullable=False, doc="Position side (yes/no)")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, doc="Number of contracts held")

    # Entry pricing
    entry_price: Mapped[float] = mapped_column(
        Float, nullable=False, doc="Average entry price in cents"
    )
    total_cost: Mapped[float] = mapped_column(
        Float, nullable=False, doc="Total cost basis in cents"
    )

    # Current valuation
    current_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Current market price in cents"
    )
    unrealized_pnl: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, doc="Unrealized profit/loss in cents"
    )

    # Position status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", doc="Position status (open/closed)"
    )

    # Settlement
    settlement_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Settlement price if closed"
    )
    realized_pnl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Realized profit/loss in cents"
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Timestamp when position closed"
    )

    # Relationship to market
    market: Mapped["Market"] = relationship("Market", backref="positions")

    __table_args__ = (
        UniqueConstraint("market_id", "side", name="uq_positions_market_side"),
        {"comment": "Open and closed trading positions"},
    )

    def __repr__(self) -> str:
        """String representation of Position."""
        return (
            f"<Position(ticker={self.ticker}, side={self.side}, "
            f"qty={self.quantity}, status={self.status})>"
        )

    def update_pnl(self, current_price: float) -> None:
        """Update unrealized P&L based on current market price.

        Args:
            current_price: Current market price in cents
        """
        self.current_price = current_price
        if self.side == "yes":
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:  # no side
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity

    def close_position(self, settlement_price: float, closed_at: datetime) -> None:
        """Close the position and calculate realized P&L.

        Args:
            settlement_price: Final settlement price in cents
            closed_at: Timestamp when position was closed
        """
        self.status = "closed"
        self.settlement_price = settlement_price
        self.closed_at = closed_at

        if self.side == "yes":
            self.realized_pnl = (settlement_price - self.entry_price) * self.quantity
        else:  # no side
            self.realized_pnl = (self.entry_price - settlement_price) * self.quantity
