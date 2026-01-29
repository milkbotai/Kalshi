"""Unit tests for Analytics API.

Tests the internal analytics API endpoints.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.analytics.api import AnalyticsAPI, APIResponse, create_analytics_api


class TestAPIResponse:
    """Tests for APIResponse dataclass."""

    def test_api_response_success(self) -> None:
        """Test successful API response."""
        response = APIResponse(
            success=True,
            data={"count": 10},
        )

        assert response.success is True
        assert response.data["count"] == 10
        assert response.error is None
        assert response.timestamp is not None

    def test_api_response_with_explicit_timestamp(self) -> None:
        """Test API response with explicit timestamp."""
        explicit_time = datetime(2026, 1, 28, 12, 0, 0, tzinfo=timezone.utc)
        response = APIResponse(
            success=True,
            data={"test": "data"},
            timestamp=explicit_time,
        )

        assert response.timestamp == explicit_time

    def test_api_response_error(self) -> None:
        """Test error API response."""
        response = APIResponse(
            success=False,
            error="Query failed",
        )

        assert response.success is False
        assert response.error == "Query failed"
        assert response.data is None

    def test_api_response_to_dict(self) -> None:
        """Test converting response to dictionary."""
        response = APIResponse(
            success=True,
            data={"metrics": []},
        )

        result = response.to_dict()

        assert result["success"] is True
        assert "timestamp" in result
        assert result["data"] == {"metrics": []}


class TestAnalyticsAPI:
    """Tests for AnalyticsAPI class."""

    @pytest.fixture
    def mock_engine(self) -> MagicMock:
        """Create mock database engine."""
        return MagicMock()

    @pytest.fixture
    def api(self, mock_engine: MagicMock) -> AnalyticsAPI:
        """Create AnalyticsAPI instance."""
        return AnalyticsAPI(mock_engine)

    def test_api_initialization(self, mock_engine: MagicMock) -> None:
        """Test API initialization."""
        api = AnalyticsAPI(mock_engine)
        assert api.engine == mock_engine

    def test_cache_hit(self, api: AnalyticsAPI) -> None:
        """Test cache hit returns cached value."""
        # Set a value in cache
        api._set_cache("test_key", "cached_value")

        # Should return cached value
        result = api._get_cached("test_key")
        assert result == "cached_value"

    def test_cache_miss(self, api: AnalyticsAPI) -> None:
        """Test cache miss returns None."""
        result = api._get_cached("nonexistent_key")
        assert result is None

    def test_cache_expiry(self, api: AnalyticsAPI) -> None:
        """Test cache expiry after TTL."""
        import datetime as dt

        # Set cache with old timestamp
        old_time = datetime.now(timezone.utc) - dt.timedelta(seconds=10)
        api._cache["expired_key"] = (old_time, "old_value")

        # Should return None (expired)
        result = api._get_cached("expired_key")
        assert result is None
        # Key should be removed
        assert "expired_key" not in api._cache

    @patch("src.analytics.rollups.get_city_metrics")
    def test_get_city_metrics_success(
        self,
        mock_get_city: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test getting city metrics successfully."""
        mock_get_city.return_value = [
            {
                "city_code": "NYC",
                "date": date(2026, 1, 28),
                "trade_count": 10,
                "net_pnl": Decimal("100.00"),
                "win_count": 7,
                "loss_count": 3,
            },
        ]

        response = api.get_city_metrics(city_code="NYC")

        assert response.success is True
        assert response.data["count"] == 1
        assert response.data["summary"]["total_trades"] == 10
        assert response.data["summary"]["win_rate"] == 70.0

    @patch("src.analytics.rollups.get_city_metrics")
    def test_get_city_metrics_empty_results(
        self,
        mock_get_city: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test city metrics with empty results."""
        mock_get_city.return_value = []

        response = api.get_city_metrics()

        assert response.success is True
        assert response.data["count"] == 0
        assert response.data["summary"]["total_pnl"] == 0
        assert response.data["summary"]["total_trades"] == 0
        assert response.data["summary"]["win_rate"] == 0

    @patch("src.analytics.rollups.get_city_metrics")
    def test_get_city_metrics_uses_cache(
        self,
        mock_get_city: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test city metrics uses cache on second call."""
        mock_get_city.return_value = [
            {"city_code": "NYC", "trade_count": 5, "net_pnl": 50, "win_count": 3, "loss_count": 2},
        ]

        # First call
        response1 = api.get_city_metrics(city_code="NYC")
        assert response1.success is True

        # Second call should use cache
        response2 = api.get_city_metrics(city_code="NYC")
        assert response2.success is True

        # Should only call the underlying function once
        assert mock_get_city.call_count == 1

    @patch("src.analytics.rollups.get_city_metrics")
    def test_get_city_metrics_error(
        self,
        mock_get_city: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test city metrics query error handling."""
        mock_get_city.side_effect = Exception("Database error")

        response = api.get_city_metrics()

        assert response.success is False
        assert "Database error" in response.error

    @patch("src.analytics.rollups.get_strategy_metrics")
    def test_get_strategy_metrics_success(
        self,
        mock_get_strategy: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test getting strategy metrics successfully."""
        mock_get_strategy.return_value = [
            {
                "strategy_name": "daily_high_temp",
                "date": date(2026, 1, 28),
                "trade_count": 15,
                "signal_count": 20,
                "net_pnl": Decimal("150.00"),
            },
        ]

        response = api.get_strategy_metrics(strategy_name="daily_high_temp")

        assert response.success is True
        assert response.data["summary"]["conversion_rate"] == 75.0

    @patch("src.analytics.rollups.get_strategy_metrics")
    def test_get_strategy_metrics_empty_results(
        self,
        mock_get_strategy: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test strategy metrics with empty results."""
        mock_get_strategy.return_value = []

        response = api.get_strategy_metrics()

        assert response.success is True
        assert response.data["summary"]["total_pnl"] == 0
        assert response.data["summary"]["conversion_rate"] == 0

    @patch("src.analytics.rollups.get_strategy_metrics")
    def test_get_strategy_metrics_error(
        self,
        mock_get_strategy: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test strategy metrics query error handling."""
        mock_get_strategy.side_effect = Exception("Strategy query failed")

        response = api.get_strategy_metrics()

        assert response.success is False
        assert "Strategy query failed" in response.error

    @patch("src.analytics.rollups.get_equity_curve")
    def test_get_equity_curve_success(
        self,
        mock_get_equity: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test getting equity curve successfully."""
        mock_get_equity.return_value = [
            {
                "date": date(2026, 1, 27),
                "starting_equity": Decimal("5000.00"),
                "ending_equity": Decimal("5100.00"),
                "daily_pnl": Decimal("100.00"),
                "cumulative_pnl": Decimal("100.00"),
                "drawdown": Decimal("0"),
                "drawdown_pct": Decimal("0"),
            },
            {
                "date": date(2026, 1, 28),
                "starting_equity": Decimal("5100.00"),
                "ending_equity": Decimal("5150.00"),
                "daily_pnl": Decimal("50.00"),
                "cumulative_pnl": Decimal("150.00"),
                "drawdown": Decimal("0"),
                "drawdown_pct": Decimal("0"),
            },
        ]

        response = api.get_equity_curve()

        assert response.success is True
        assert response.data["summary"]["trading_days"] == 2
        assert response.data["summary"]["total_return"] == 150.0

    @patch("src.analytics.rollups.get_equity_curve")
    def test_get_equity_curve_empty_results(
        self,
        mock_get_equity: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test equity curve with empty results."""
        mock_get_equity.return_value = []

        response = api.get_equity_curve()

        assert response.success is True
        assert response.data["summary"]["trading_days"] == 0
        assert response.data["summary"]["total_return"] == 0
        assert response.data["summary"]["max_drawdown"] == 0

    @patch("src.analytics.rollups.get_equity_curve")
    def test_get_equity_curve_error(
        self,
        mock_get_equity: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test equity curve query error handling."""
        mock_get_equity.side_effect = Exception("Equity curve query failed")

        response = api.get_equity_curve()

        assert response.success is False
        assert "Equity curve query failed" in response.error

    @patch("src.analytics.rollups.get_equity_curve")
    def test_get_equity_curve_uses_cache(
        self,
        mock_get_equity: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test equity curve uses cache on second call."""
        mock_get_equity.return_value = [
            {"date": date(2026, 1, 28), "starting_equity": 5000, "ending_equity": 5100,
             "daily_pnl": 100, "cumulative_pnl": 100, "drawdown": 0, "drawdown_pct": 0},
        ]

        # First call
        response1 = api.get_equity_curve()
        assert response1.success is True

        # Second call should use cache
        response2 = api.get_equity_curve()
        assert response2.success is True

        # Should only call the underlying function once
        assert mock_get_equity.call_count == 1

    @patch("src.shared.db.analytics.get_public_trades")
    def test_get_public_trades_success(
        self,
        mock_get_trades: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test getting public trades successfully."""
        mock_get_trades.return_value = [
            {"trade_id": 1, "ticker": "HIGHNYC-25JAN26-T42", "side": "yes"},
        ]

        response = api.get_public_trades(city_code="NYC", limit=10)

        assert response.success is True
        assert response.data["count"] == 1
        assert response.data["delay_minutes"] == 60

    @patch("src.shared.db.analytics.get_public_trades")
    def test_get_public_trades_error(
        self,
        mock_get_trades: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test public trades query error handling."""
        mock_get_trades.side_effect = Exception("Trades query failed")

        response = api.get_public_trades()

        assert response.success is False
        assert "Trades query failed" in response.error

    @patch("src.analytics.health.get_current_health")
    def test_get_health_status_success(
        self,
        mock_get_health: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test getting health status successfully."""
        from src.analytics.health import ComponentHealth, ComponentStatus, SystemHealth

        mock_get_health.return_value = SystemHealth(
            checked_at=datetime.now(timezone.utc),
            overall_status=ComponentStatus.HEALTHY,
            components=[
                ComponentHealth(
                    name="kalshi_api",
                    status=ComponentStatus.HEALTHY,
                    last_check=datetime.now(timezone.utc),
                    latency_ms=50.0,
                ),
            ],
            total_healthy=1,
            total_degraded=0,
            total_unhealthy=0,
        )

        response = api.get_health_status()

        assert response.success is True
        assert response.data["overall_status"] == "healthy"
        assert len(response.data["components"]) == 1

    @patch("src.analytics.health.get_current_health")
    def test_get_health_status_error(
        self,
        mock_get_health: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test health status query error handling."""
        mock_get_health.side_effect = Exception("Health check failed")

        response = api.get_health_status()

        assert response.success is False
        assert "Health check failed" in response.error

    @patch("src.analytics.health.check_degraded_components")
    def test_get_degraded_components_success(
        self,
        mock_check_degraded: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test getting degraded components."""
        from src.analytics.health import ComponentHealth, ComponentStatus

        mock_check_degraded.return_value = [
            ComponentHealth(
                name="weather_api",
                status=ComponentStatus.DEGRADED,
                last_check=datetime.now(timezone.utc),
                latency_ms=500.0,
                message="High latency",
            ),
        ]

        response = api.get_degraded_components()

        assert response.success is True
        assert response.data["count"] == 1
        assert response.data["degraded_components"][0]["name"] == "weather_api"

    @patch("src.analytics.health.check_degraded_components")
    def test_get_degraded_components_error(
        self,
        mock_check_degraded: MagicMock,
        api: AnalyticsAPI,
    ) -> None:
        """Test degraded components query error handling."""
        mock_check_degraded.side_effect = Exception("Degraded check failed")

        response = api.get_degraded_components()

        assert response.success is False
        assert "Degraded check failed" in response.error

    def test_get_dashboard_summary(self, api: AnalyticsAPI) -> None:
        """Test getting dashboard summary."""
        # Mock all sub-methods
        with patch.object(api, "get_city_metrics") as mock_city, \
             patch.object(api, "get_strategy_metrics") as mock_strategy, \
             patch.object(api, "get_equity_curve") as mock_equity, \
             patch.object(api, "get_health_status") as mock_health:

            mock_city.return_value = APIResponse(
                success=True,
                data={"summary": {"total_pnl": 100, "win_rate": 70}},
            )
            mock_strategy.return_value = APIResponse(
                success=True,
                data={"summary": {"conversion_rate": 75}},
            )
            mock_equity.return_value = APIResponse(
                success=True,
                data={"summary": {"total_return": 150}},
            )
            mock_health.return_value = APIResponse(
                success=True,
                data={"overall_status": "healthy", "summary": {"total_healthy": 3}},
            )

            response = api.get_dashboard_summary()

            assert response.success is True
            assert response.data["overall_health"] == "healthy"
            assert response.data["city_summary"]["total_pnl"] == 100

    def test_get_dashboard_summary_with_failures(self, api: AnalyticsAPI) -> None:
        """Test dashboard summary handles sub-query failures gracefully."""
        with patch.object(api, "get_city_metrics") as mock_city, \
             patch.object(api, "get_strategy_metrics") as mock_strategy, \
             patch.object(api, "get_equity_curve") as mock_equity, \
             patch.object(api, "get_health_status") as mock_health:

            # Some queries fail
            mock_city.return_value = APIResponse(success=False, error="City query failed")
            mock_strategy.return_value = APIResponse(success=False, error="Strategy query failed")
            mock_equity.return_value = APIResponse(success=True, data={"summary": {"total_return": 100}})
            mock_health.return_value = APIResponse(success=False, error="Health query failed")

            response = api.get_dashboard_summary()

            # Should still succeed overall
            assert response.success is True
            # Failed queries return empty dicts
            assert response.data["city_summary"] == {}
            assert response.data["strategy_summary"] == {}
            assert response.data["overall_health"] == "unknown"

    def test_get_dashboard_summary_error(self, api: AnalyticsAPI) -> None:
        """Test dashboard summary handles exception."""
        with patch.object(api, "get_city_metrics") as mock_city:
            mock_city.side_effect = Exception("Unexpected error")

            response = api.get_dashboard_summary()

            assert response.success is False
            assert "Unexpected error" in response.error


class TestCreateAnalyticsAPI:
    """Tests for factory function."""

    def test_create_analytics_api(self) -> None:
        """Test creating analytics API via factory."""
        mock_engine = MagicMock()

        api = create_analytics_api(mock_engine)

        assert isinstance(api, AnalyticsAPI)
        assert api.engine == mock_engine
