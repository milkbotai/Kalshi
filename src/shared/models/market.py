"""Market model for Kalshi trading markets.

Represents a Kalshi market with pricing, volume, and metadata.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.base import Base, TimestampMixin


class Market(Base, TimestampMixin):
    """Kalshi market model.
    
    Stores market data including ticker, pricing, volume, and settlement information.
    Updated periodically from Kalshi API.
    """

    __tablename__ = "markets"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Market identifiers
    ticker: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, doc="Kalshi market ticker"
    )
    event_ticker: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, doc="Parent event ticker"
    )

    # Market metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False, doc="Market title")
    city_code: Mapped[str] = mapped_column(
        String(3), nullable=False, index=True, doc="3-letter city code"
    )
    market_type: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="Market type (high/low)"
    )

    # Pricing data (in cents, 0-100)
    yes_bid: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Current yes bid price in cents"
    )
    yes_ask: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Current yes ask price in cents"
    )
    no_bid: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Current no bid price in cents"
    )
    no_ask: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Current no ask price in cents"
    )
    last_price: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Last traded price in cents"
    )

    # Volume and liquidity
    volume: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, doc="Total volume traded"
    )
    open_interest: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, doc="Current open interest"
    )

    # Market status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", doc="Market status"
    )
    can_close_early: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, doc="Whether market can close early"
    )

    # Settlement
    settlement_value: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, doc="Settlement value (0 or 100)"
    )
    settlement_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Date market settles"
    )
    close_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Date market closes for trading"
    )
    expiration_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Market expiration date"
    )

    # Strike price for temperature markets
    strike_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Strike temperature in Fahrenheit"
    )

    # Timestamps for data freshness
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="Last time market data was updated"
    )

    __table_args__ = (
        UniqueConstraint("ticker", name="uq_markets_ticker"),
        {"comment": "Kalshi trading markets with pricing and volume data"},
    )

    def __repr__(self) -> str:
        """String representation of Market."""
        return f"<Market(ticker={self.ticker}, city={self.city_code}, status={self.status})>"

    @property
    def spread_bps(self) -> Optional[int]:
        """Calculate bid-ask spread in basis points.
        
        Returns:
            Spread in basis points, or None if pricing unavailable
        """
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_ask - self.yes_bid) * 100
        return None

    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price between bid and ask.
        
        Returns:
            Mid price in cents, or None if pricing unavailable
        """
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2.0
        return None
