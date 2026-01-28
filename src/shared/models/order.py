"""Order model for tracking trade orders.

Represents orders submitted to Kalshi exchange.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.shared.models.market import Market


class Order(Base, TimestampMixin):
    """Trading order model.

    Tracks orders submitted to Kalshi including status, fills, and execution details.
    """

    __tablename__ = "orders"

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

    # Order identifiers
    order_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True, doc="Kalshi order ID"
    )
    ticker: Mapped[str] = mapped_column(String(50), nullable=False, index=True, doc="Market ticker")

    # Order details
    side: Mapped[str] = mapped_column(String(10), nullable=False, doc="Order side (yes/no)")
    action: Mapped[str] = mapped_column(String(10), nullable=False, doc="Order action (buy/sell)")
    order_type: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="Order type (limit/market)"
    )

    # Quantity and pricing
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, doc="Order quantity")
    limit_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Limit price in cents"
    )
    filled_quantity: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, doc="Quantity filled"
    )
    remaining_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="Quantity remaining"
    )

    # Execution details
    average_fill_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Average fill price in cents"
    )
    total_cost: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, doc="Total cost of filled quantity"
    )

    # Order status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", doc="Order status"
    )
    status_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="Status message or error details"
    )

    # Timestamps
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="When order was submitted"
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When order was fully filled"
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When order was cancelled"
    )

    # Strategy context
    strategy_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, doc="Name of strategy that created order"
    )
    signal_strength: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Signal strength that triggered order"
    )

    # Relationship to market
    market: Mapped["Market"] = relationship("Market", backref="orders")

    __table_args__ = ({"comment": "Trading orders submitted to Kalshi"},)

    def __repr__(self) -> str:
        """String representation of Order."""
        return (
            f"<Order(ticker={self.ticker}, side={self.side}, "
            f"qty={self.quantity}, status={self.status})>"
        )

    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled.

        Returns:
            True if order is completely filled
        """
        return self.filled_quantity == self.quantity

    @property
    def fill_rate(self) -> float:
        """Calculate fill rate as percentage.

        Returns:
            Fill rate from 0.0 to 1.0
        """
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity

    def update_fill(self, filled_quantity: int, average_price: float, filled_at: datetime) -> None:
        """Update order with fill information.

        Args:
            filled_quantity: Total quantity filled
            average_price: Average fill price in cents
            filled_at: Timestamp of fill
        """
        self.filled_quantity = filled_quantity
        self.remaining_quantity = self.quantity - filled_quantity
        self.average_fill_price = average_price
        self.total_cost = filled_quantity * average_price

        if self.is_filled:
            self.status = "filled"
            self.filled_at = filled_at
        else:
            self.status = "partially_filled"
