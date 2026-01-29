"""Unit tests for health metrics aggregation.

Tests the health monitoring and component status tracking.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.analytics.health import (
    ComponentHealth,
    ComponentStatus,
    SystemHealth,
    check_degraded_components,
    cleanup_old_health_records,
    create_health_tables,
    get_current_health,
    get_health_history,
    record_health_check,
)


class TestComponentHealth:
    """Tests for ComponentHealth dataclass."""

    def test_component_health_creation(self) -> None:
        """Test creating component health."""
        health = ComponentHealth(
            name="kalshi_api",
            status=ComponentStatus.HEALTHY,
            last_check=datetime.now(timezone.utc),
            latency_ms=45.5,
            error_rate=0.01,
            message="All systems operational",
        )

        assert health.name == "kalshi_api"
        assert health.is_healthy is True
        assert health.is_degraded is False

    def test_component_health_degraded(self) -> None:
        """Test degraded component status."""
        health = ComponentHealth(
            name="weather_api",
            status=ComponentStatus.DEGRADED,
            last_check=datetime.now(timezone.utc),
            latency_ms=500.0,
            error_rate=0.05,
            message="High latency detected",
        )

        assert health.is_healthy is False
        assert health.is_degraded is True

    def test_component_health_unhealthy(self) -> None:
        """Test unhealthy component status."""
        health = ComponentHealth(
            name="database",
            status=ComponentStatus.UNHEALTHY,
            last_check=datetime.now(timezone.utc),
            error_rate=0.5,
            message="Connection failures",
        )

        assert health.is_healthy is False
        assert health.is_degraded is False


class TestSystemHealth:
    """Tests for SystemHealth dataclass."""

    def test_system_health_all_healthy(self) -> None:
        """Test system health when all components are healthy."""
        components = [
            ComponentHealth(
                name="api",
                status=ComponentStatus.HEALTHY,
                last_check=datetime.now(timezone.utc),
            ),
            ComponentHealth(
                name="db",
                status=ComponentStatus.HEALTHY,
                last_check=datetime.now(timezone.utc),
            ),
        ]

        health = SystemHealth(
            checked_at=datetime.now(timezone.utc),
            overall_status=ComponentStatus.HEALTHY,
            components=components,
            total_healthy=2,
            total_degraded=0,
            total_unhealthy=0,
        )

        assert health.is_system_healthy is True
        assert health.total_healthy == 2

    def test_system_health_with_degraded(self) -> None:
        """Test system health with degraded component."""
        health = SystemHealth(
            checked_at=datetime.now(timezone.utc),
            overall_status=ComponentStatus.DEGRADED,
            components=[],
            total_healthy=1,
            total_degraded=1,
            total_unhealthy=0,
        )

        assert health.is_system_healthy is False

    def test_system_health_with_unhealthy(self) -> None:
        """Test system health with unhealthy component."""
        health = SystemHealth(
            checked_at=datetime.now(timezone.utc),
            overall_status=ComponentStatus.UNHEALTHY,
            components=[],
            total_healthy=1,
            total_degraded=0,
            total_unhealthy=1,
        )

        assert health.is_system_healthy is False


class TestHealthTableCreation:
    """Tests for health table creation."""

    def test_create_health_tables(self) -> None:
        """Test creating health tables."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        create_health_tables(mock_engine)

        assert mock_conn.execute.called
        assert mock_conn.commit.called


class TestHealthRecording:
    """Tests for recording health checks."""

    def test_record_health_check(self) -> None:
        """Test recording a health check."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        record_health_check(
            mock_engine,
            component_name="kalshi_api",
            status=ComponentStatus.HEALTHY,
            latency_ms=50.0,
            error_count=0,
            request_count=100,
            message="OK",
        )

        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_record_health_check_with_errors(self) -> None:
        """Test recording health check with errors."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        record_health_check(
            mock_engine,
            component_name="weather_api",
            status=ComponentStatus.DEGRADED,
            latency_ms=200.0,
            error_count=5,
            request_count=100,
            message="High error rate",
            details={"endpoint": "/forecast"},
        )

        mock_conn.execute.assert_called_once()


class TestHealthQueries:
    """Tests for health query functions."""

    def test_get_current_health(self) -> None:
        """Test getting current health status."""
        # Mock row data
        mock_rows = [
            ("kalshi_api", "healthy", datetime.now(timezone.utc), 50.0, 0.01, "OK", {}),
            ("weather_api", "degraded", datetime.now(timezone.utc), 200.0, 0.05, "Slow", {}),
        ]

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(mock_rows))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        health = get_current_health(mock_engine)

        assert len(health.components) == 2
        assert health.total_healthy == 1
        assert health.total_degraded == 1
        assert health.overall_status == ComponentStatus.DEGRADED

    def test_get_current_health_all_healthy(self) -> None:
        """Test getting health when all components healthy."""
        mock_rows = [
            ("api", "healthy", datetime.now(timezone.utc), 50.0, 0.0, "OK", {}),
            ("db", "healthy", datetime.now(timezone.utc), 10.0, 0.0, "OK", {}),
        ]

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(mock_rows))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        health = get_current_health(mock_engine)

        assert health.overall_status == ComponentStatus.HEALTHY
        assert health.is_system_healthy is True

    def test_get_health_history(self) -> None:
        """Test getting health history."""
        mock_rows = [
            ("kalshi_api", "healthy", datetime.now(timezone.utc), 50.0, 0.01, "OK"),
        ]

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(mock_rows))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        history = get_health_history(mock_engine, component_name="kalshi_api", hours=24)

        assert len(history) == 1
        assert history[0]["component_name"] == "kalshi_api"

    def test_check_degraded_components(self) -> None:
        """Test checking for degraded components."""
        mock_rows = [
            ("api", "healthy", datetime.now(timezone.utc), 50.0, 0.0, "OK", {}),
            ("db", "degraded", datetime.now(timezone.utc), 500.0, 0.1, "Slow", {}),
            ("cache", "unhealthy", datetime.now(timezone.utc), None, 0.5, "Down", {}),
        ]

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(mock_rows))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        degraded = check_degraded_components(mock_engine)

        assert len(degraded) == 2
        names = [c.name for c in degraded]
        assert "db" in names
        assert "cache" in names


class TestHealthCleanup:
    """Tests for health record cleanup."""

    def test_cleanup_old_health_records(self) -> None:
        """Test cleaning up old health records."""
        mock_result = MagicMock()
        mock_result.rowcount = 100

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        deleted = cleanup_old_health_records(mock_engine, days=7)

        assert deleted == 100
        mock_conn.commit.assert_called_once()
