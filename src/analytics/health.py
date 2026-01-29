"""System health metrics aggregation.

Provides a view for system health dashboard with component status,
latency metrics, and error rates.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.shared.config.logging import get_logger

logger = get_logger(__name__)


class ComponentStatus(Enum):
    """Health status for a component."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status for a single component."""

    name: str
    status: ComponentStatus
    last_check: datetime
    latency_ms: float | None = None
    error_rate: float | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if component is healthy."""
        return self.status == ComponentStatus.HEALTHY

    @property
    def is_degraded(self) -> bool:
        """Check if component is degraded."""
        return self.status == ComponentStatus.DEGRADED


@dataclass
class SystemHealth:
    """Aggregated system health status."""

    checked_at: datetime
    overall_status: ComponentStatus
    components: list[ComponentHealth]
    total_healthy: int = 0
    total_degraded: int = 0
    total_unhealthy: int = 0

    @property
    def is_system_healthy(self) -> bool:
        """Check if overall system is healthy."""
        return self.overall_status == ComponentStatus.HEALTHY


# SQL for creating health metrics table/view
HEALTH_METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analytics.health_metrics (
    id SERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latency_ms DECIMAL(10, 2),
    error_count INTEGER DEFAULT 0,
    request_count INTEGER DEFAULT 0,
    error_rate DECIMAL(5, 4),
    message TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT valid_status CHECK (status IN ('healthy', 'degraded', 'unhealthy', 'unknown'))
);

CREATE INDEX IF NOT EXISTS idx_health_metrics_component
ON analytics.health_metrics(component_name);

CREATE INDEX IF NOT EXISTS idx_health_metrics_checked_at
ON analytics.health_metrics(checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_health_metrics_status
ON analytics.health_metrics(status);

COMMENT ON TABLE analytics.health_metrics IS
'System health metrics for dashboard monitoring';
"""

# View for latest health status per component (optimized for dashboard)
HEALTH_VIEW_SQL = """
CREATE OR REPLACE VIEW analytics.v_current_health AS
SELECT DISTINCT ON (component_name)
    component_name,
    status,
    checked_at,
    latency_ms,
    error_rate,
    message,
    details
FROM analytics.health_metrics
ORDER BY component_name, checked_at DESC;

COMMENT ON VIEW analytics.v_current_health IS
'Latest health status for each component, optimized for dashboard queries';
"""


def create_health_tables(engine: Engine) -> None:
    """Create health metrics table and view.

    Args:
        engine: SQLAlchemy engine instance
    """
    # Ensure analytics schema exists
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
        conn.commit()

    # Create health metrics table
    with engine.connect() as conn:
        for statement in HEALTH_METRICS_TABLE_SQL.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()

    # Create health view
    with engine.connect() as conn:
        for statement in HEALTH_VIEW_SQL.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()

    logger.info("health_tables_created")


def record_health_check(
    engine: Engine,
    component_name: str,
    status: ComponentStatus,
    latency_ms: float | None = None,
    error_count: int = 0,
    request_count: int = 0,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Record a health check result.

    Args:
        engine: SQLAlchemy engine instance
        component_name: Name of the component
        status: Health status
        latency_ms: Optional latency in milliseconds
        error_count: Number of errors in check period
        request_count: Total requests in check period
        message: Optional status message
        details: Optional additional details
    """
    error_rate = None
    if request_count > 0:
        error_rate = error_count / request_count

    insert_sql = """
    INSERT INTO analytics.health_metrics (
        component_name, status, checked_at, latency_ms,
        error_count, request_count, error_rate, message, details
    ) VALUES (
        :component_name, :status, :checked_at, :latency_ms,
        :error_count, :request_count, :error_rate, :message, :details
    )
    """

    with engine.connect() as conn:
        conn.execute(
            text(insert_sql),
            {
                "component_name": component_name,
                "status": status.value,
                "checked_at": datetime.now(timezone.utc),
                "latency_ms": latency_ms,
                "error_count": error_count,
                "request_count": request_count,
                "error_rate": error_rate,
                "message": message,
                "details": details or {},
            },
        )
        conn.commit()

    logger.debug(
        "health_check_recorded",
        component=component_name,
        status=status.value,
        latency_ms=latency_ms,
    )


def get_current_health(engine: Engine) -> SystemHealth:
    """Get current health status for all components.

    Queries the v_current_health view for latest status.
    Query is optimized to complete in <50ms.

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        SystemHealth with all component statuses
    """
    query = """
    SELECT
        component_name,
        status,
        checked_at,
        latency_ms,
        error_rate,
        message,
        details
    FROM analytics.v_current_health
    ORDER BY component_name
    """

    components: list[ComponentHealth] = []

    with engine.connect() as conn:
        result = conn.execute(text(query))

        for row in result:
            status = ComponentStatus(row[1]) if row[1] else ComponentStatus.UNKNOWN
            components.append(
                ComponentHealth(
                    name=row[0],
                    status=status,
                    last_check=row[2],
                    latency_ms=float(row[3]) if row[3] else None,
                    error_rate=float(row[4]) if row[4] else None,
                    message=row[5],
                    details=row[6] or {},
                )
            )

    # Calculate aggregates
    healthy = sum(1 for c in components if c.status == ComponentStatus.HEALTHY)
    degraded = sum(1 for c in components if c.status == ComponentStatus.DEGRADED)
    unhealthy = sum(1 for c in components if c.status == ComponentStatus.UNHEALTHY)

    # Determine overall status
    if unhealthy > 0:
        overall = ComponentStatus.UNHEALTHY
    elif degraded > 0:
        overall = ComponentStatus.DEGRADED
    elif healthy > 0:
        overall = ComponentStatus.HEALTHY
    else:
        overall = ComponentStatus.UNKNOWN

    return SystemHealth(
        checked_at=datetime.now(timezone.utc),
        overall_status=overall,
        components=components,
        total_healthy=healthy,
        total_degraded=degraded,
        total_unhealthy=unhealthy,
    )


def get_health_history(
    engine: Engine,
    component_name: str | None = None,
    hours: int = 24,
) -> list[dict[str, Any]]:
    """Get health check history.

    Args:
        engine: SQLAlchemy engine instance
        component_name: Optional filter by component
        hours: Number of hours of history to return

    Returns:
        List of health check records
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = """
    SELECT
        component_name,
        status,
        checked_at,
        latency_ms,
        error_rate,
        message
    FROM analytics.health_metrics
    WHERE checked_at >= :cutoff
    """
    params: dict[str, Any] = {"cutoff": cutoff}

    if component_name:
        query += " AND component_name = :component_name"
        params["component_name"] = component_name

    query += " ORDER BY checked_at DESC LIMIT 1000"

    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [
            {
                "component_name": row[0],
                "status": row[1],
                "checked_at": row[2],
                "latency_ms": float(row[3]) if row[3] else None,
                "error_rate": float(row[4]) if row[4] else None,
                "message": row[5],
            }
            for row in result
        ]


def check_degraded_components(engine: Engine) -> list[ComponentHealth]:
    """Get list of degraded or unhealthy components.

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        List of degraded/unhealthy components
    """
    health = get_current_health(engine)
    return [
        c for c in health.components
        if c.status in (ComponentStatus.DEGRADED, ComponentStatus.UNHEALTHY)
    ]


def cleanup_old_health_records(engine: Engine, days: int = 7) -> int:
    """Clean up old health records.

    Args:
        engine: SQLAlchemy engine instance
        days: Number of days to retain

    Returns:
        Number of records deleted
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    delete_sql = """
    DELETE FROM analytics.health_metrics
    WHERE checked_at < :cutoff
    """

    with engine.connect() as conn:
        result = conn.execute(text(delete_sql), {"cutoff": cutoff})
        deleted = result.rowcount
        conn.commit()

    logger.info(
        "health_records_cleaned",
        deleted=deleted,
        retention_days=days,
    )

    return deleted
