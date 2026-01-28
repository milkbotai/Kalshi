"""Trade model for executed trades.

Represents individual trade executions from filled orders.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.shared.models.market import Market
    from src.shared.models.order import Order


class Trade(Base, TimestampMixin):
    """Trade execution model.

    Records individual trade executions with pricing and P&L tracking.
    """

    __tablename__ = "trades"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    market_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to market",
    )
    order_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Reference to originating order",
    )

    # Trade identifiers
    trade_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True, doc="Kalshi trade ID"
    )
    ticker: Mapped[str] = mapped_column(String(50), nullable=False, index=True, doc="Market ticker")

    # Trade details
    side: Mapped[str] = mapped_column(String(10), nullable=False, doc="Trade side (yes/no)")
    action: Mapped[str] = mapped_column(String(10), nullable=False, doc="Trade action (buy/sell)")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, doc="Quantity traded")
    price: Mapped[float] = mapped_column(Float, nullable=False, doc="Execution price in cents")

    # Costs and fees
    total_cost: Mapped[float] = mapped_column(
        Float, nullable=False, doc="Total cost including fees"
    )
    fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, doc="Trading fees")

    # P&L tracking
    realized_pnl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Realized P&L if position closed"
    )
    exit_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Exit price if trade closed position"
    )

    # Execution timestamp
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="When trade was executed"
    )

    # Strategy context
    strategy_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, doc="Strategy that generated trade"
    )

    # Relationships
    market: Mapped["Market"] = relationship("Market", backref="trades")
    order: Mapped[Optional["Order"]] = relationship("Order", backref="trades")

    __table_args__ = ({"comment": "Executed trades with P&L tracking"},)

    def __repr__(self) -> str:
        """String representation of Trade."""
        return (
            f"<Trade(ticker={self.ticker}, side={self.side}, "
            f"qty={self.quantity}, price={self.price})>"
        )

    @property
    def notional_value(self) -> float:
        """Calculate notional value of trade.

        Returns:
            Notional value in cents
        """
        return self.quantity * self.price

    def calculate_pnl(self, exit_price: float) -> float:
        """Calculate P&L for closing this trade.

        Args:
            exit_price: Exit price in cents

        Returns:
            Profit or loss in cents
        """
        if self.action == "buy":
            pnl = (exit_price - self.price) * self.quantity
        else:  # sell
            pnl = (self.price - exit_price) * self.quantity

        return pnl - self.fees
