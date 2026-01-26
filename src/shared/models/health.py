"""Health status model for system component monitoring.

Tracks health status of trader, analytics, dashboard, and external APIs.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.base import Base, TimestampMixin


class HealthStatus(Base, TimestampMixin):
    """System health status model.
    
    Tracks health of individual system components for monitoring and alerting.
    """

    __tablename__ = "health_status"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Component identifier
    component: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        doc="Component name (trader, analytics, dashboard, kalshi_api, nws_api, database)",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="Status (OK, DEGRADED, DOWN)"
    )

    # Timestamps
    last_ok: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="Last time component was healthy"
    )

    last_check: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="Last health check time"
    )

    # Details
    message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Status message or error details"
    )

    __table_args__ = ({"comment": "System component health status"},)

    def __repr__(self) -> str:
        """String representation of HealthStatus."""
        return f"<HealthStatus(component={self.component}, status={self.status})>"

    @property
    def is_healthy(self) -> bool:
        """Check if component is healthy.
        
        Returns:
            True if status is OK
        """
        return self.status == "OK"

    @property
    def downtime_seconds(self) -> float:
        """Calculate downtime in seconds.
        
        Returns:
            Seconds since last OK status
        """
        from src.shared.models.base import utcnow

        return (utcnow() - self.last_ok).total_seconds()
