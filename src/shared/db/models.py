"""SQLAlchemy ORM models for the ops schema.

Defines database tables for weather snapshots, market snapshots, signals,
orders, fills, positions, risk events, and health status.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# ============================================================================
# Enums
# ============================================================================


class OrderStatus(PyEnum):
    """Order status enum."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    RESTING = "resting"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    CLOSED = "closed"


class TradingModeEnum(PyEnum):
    """Trading mode enum."""

    SHADOW = "shadow"
    DEMO = "demo"
    LIVE = "live"


class RiskSeverity(PyEnum):
    """Risk event severity enum."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class HealthStatus(PyEnum):
    """Component health status enum."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ============================================================================
# Weather & Market Snapshots
# ============================================================================


class WeatherSnapshot(Base):
    """Weather snapshot from NWS API.

    Stores forecast and observation data for a city at a point in time.
    """

    __tablename__ = "weather_snapshots"
    __table_args__ = (
        Index("idx_weather_city_captured", "city_code", "captured_at"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    forecast_high: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forecast_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_forecast: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_observation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="nws")
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class MarketSnapshot(Base):
    """Market snapshot from Kalshi API.

    Stores orderbook and market data for a ticker at a point in time.
    """

    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("idx_market_ticker_captured", "ticker", "captured_at"),
        Index("idx_market_city_captured", "city_code", "captured_at"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    event_ticker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    yes_bid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yes_ask: Mapped[int | None] = mapped_column(Integer, nullable=True)
    no_bid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    no_ask: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_interest: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    strike_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiration_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    @property
    def spread_cents(self) -> int | None:
        """Calculate bid-ask spread."""
        if self.yes_bid is not None and self.yes_ask is not None:
            return self.yes_ask - self.yes_bid
        return None


# ============================================================================
# Trading Tables
# ============================================================================


class Signal(Base):
    """Trading signal generated by strategy evaluation.

    Stores probability estimates, edge calculations, and trading decisions.
    """

    __tablename__ = "signals"
    __table_args__ = (
        Index("idx_signal_ticker_created", "ticker", "created_at"),
        Index("idx_signal_city_created", "city_code", "created_at"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    side: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "yes" or "no"
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # "BUY", "SELL", "HOLD"
    p_yes: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    edge: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    features: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    weather_snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_snapshot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trading_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="shadow")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class Order(Base):
    """Trading order with idempotency support.

    Tracks order lifecycle from creation through fill/cancel/reject.
    Uses intent_key for idempotent order creation.
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("intent_key", name="uq_order_intent_key"),
        UniqueConstraint("kalshi_order_id", name="uq_order_kalshi_id"),
        Index("idx_order_ticker_created", "ticker", "created_at"),
        Index("idx_order_city_created", "city_code", "created_at"),
        Index("idx_order_status", "status"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    ticker: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    market_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    signal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kalshi_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    client_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # "yes" or "no"
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # "buy" or "sell"
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OrderStatus.PENDING.value
    )
    filled_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remaining_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_p_yes: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_edge: Mapped[float | None] = mapped_column(Float, nullable=True)
    trading_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="shadow")
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Fill(Base):
    """Trade execution (fill) record.

    Records individual fills against orders.
    """

    __tablename__ = "fills"
    __table_args__ = (
        Index("idx_fill_order_id", "order_id"),
        Index("idx_fill_ticker_time", "ticker", "fill_time"),
        Index("idx_fill_city_time", "city_code", "fill_time"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kalshi_fill_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kalshi_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ticker: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    notional_value: Mapped[float] = mapped_column(Float, nullable=False)
    fees: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    trading_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="shadow")
    fill_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class Position(Base):
    """Current position in a market.

    Tracks open and closed positions with cost basis.
    """

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("ticker", "city_code", "trading_mode", name="uq_position_ticker_city_mode"),
        Index("idx_position_city", "city_code"),
        Index("idx_position_status", "is_closed"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fees_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trading_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="shadow")
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def average_entry_price(self) -> float | None:
        """Calculate average entry price."""
        if self.quantity != 0:
            return self.total_cost / abs(self.quantity)
        return None


# ============================================================================
# Risk & Health
# ============================================================================


class RiskEvent(Base):
    """Risk event log entry.

    Records risk-related events including limit breaches, circuit breaker triggers, etc.
    """

    __tablename__ = "risk_events"
    __table_args__ = (
        Index("idx_risk_event_severity_time", "severity", "event_time"),
        Index("idx_risk_event_type_time", "event_type", "event_time"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    city_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class ComponentHealth(Base):
    """Component health status.

    Tracks health of system components (trader, analytics, dashboard, APIs).
    """

    __tablename__ = "component_health"
    __table_args__ = (
        UniqueConstraint("component_name", name="uq_component_name"),
        Index("idx_component_status", "status"),
        {"schema": "ops"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    component_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="healthy")
    last_ok: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
