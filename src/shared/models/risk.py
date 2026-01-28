"""Risk event model for tracking risk violations and circuit breakers.

Records risk events like limit breaches and trading pauses.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.base import Base, TimestampMixin


class RiskEvent(Base, TimestampMixin):
    """Risk event model.

    Tracks risk violations, circuit breaker triggers, and other risk-related events.
    """

    __tablename__ = "risk_events"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Event timestamp
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, doc="When event occurred"
    )

    # Event classification
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Event type (DAILY_LIMIT_HIT, CLUSTER_CAP, etc.)",
    )

    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, doc="Severity (INFO, WARNING, CRITICAL)"
    )

    # Event details
    message: Mapped[str] = mapped_column(Text, nullable=False, doc="Human-readable message")

    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Additional event data"
    )

    # Context
    city_code: Mapped[str | None] = mapped_column(
        String(3), nullable=True, index=True, doc="Related city if applicable"
    )

    market_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Related market if applicable"
    )

    # Resolution
    resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default=text("false"),
        doc="Whether event has been resolved",
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When event was resolved"
    )

    __table_args__ = ({"comment": "Risk events and circuit breaker triggers"},)

    def __repr__(self) -> str:
        """String representation of RiskEvent."""
        return (
            f"<RiskEvent(type={self.event_type}, severity={self.severity}, time={self.event_time})>"
        )
