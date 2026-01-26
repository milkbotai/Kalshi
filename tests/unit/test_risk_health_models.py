"""Unit tests for RiskEvent and HealthStatus models."""

from datetime import timedelta

from src.shared.models import HealthStatus, RiskEvent, utcnow


class TestRiskEventModel:
    """Test suite for RiskEvent model."""

    def test_risk_event_creation(self) -> None:
        """Test creating a RiskEvent instance."""
        event = RiskEvent(
            event_time=utcnow(),
            event_type="DAILY_LIMIT_HIT",
            severity="CRITICAL",
            message="Daily loss limit exceeded",
            payload={"loss_amount": 250.0, "limit": 250.0},
            city_code="NYC",
        )

        assert event.event_type == "DAILY_LIMIT_HIT"
        assert event.severity == "CRITICAL"
        assert event.resolved is None  # Will be False after INSERT to database

    def test_risk_event_repr(self) -> None:
        """Test RiskEvent string representation."""
        event = RiskEvent(
            event_time=utcnow(),
            event_type="CLUSTER_CAP",
            severity="WARNING",
            message="Cluster exposure limit approached",
        )

        repr_str = repr(event)
        assert "CLUSTER_CAP" in repr_str
        assert "WARNING" in repr_str


class TestHealthStatusModel:
    """Test suite for HealthStatus model."""

    def test_health_status_creation(self) -> None:
        """Test creating a HealthStatus instance."""
        now = utcnow()
        status = HealthStatus(
            component="trader",
            status="OK",
            last_ok=now,
            last_check=now,
            message="All systems operational",
        )

        assert status.component == "trader"
        assert status.status == "OK"
        assert status.is_healthy is True

    def test_health_status_is_healthy_false(self) -> None:
        """Test is_healthy returns False for degraded status."""
        status = HealthStatus(
            component="kalshi_api",
            status="DEGRADED",
            last_ok=utcnow() - timedelta(minutes=5),
            last_check=utcnow(),
        )

        assert status.is_healthy is False

    def test_health_status_downtime_seconds(self) -> None:
        """Test downtime calculation."""
        last_ok = utcnow() - timedelta(minutes=10)
        status = HealthStatus(
            component="nws_api",
            status="DOWN",
            last_ok=last_ok,
            last_check=utcnow(),
        )

        downtime = status.downtime_seconds
        assert downtime >= 600  # At least 10 minutes
        assert downtime < 610  # Less than 10 minutes + 10 seconds

    def test_health_status_repr(self) -> None:
        """Test HealthStatus string representation."""
        status = HealthStatus(
            component="database",
            status="OK",
            last_ok=utcnow(),
            last_check=utcnow(),
        )

        repr_str = repr(status)
        assert "database" in repr_str
        assert "OK" in repr_str
