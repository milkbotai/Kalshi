"""Unit tests for dashboard data provider.

Tests the data provider layer for the Streamlit dashboard.
Note: Streamlit component tests require different testing approach
and are typically done with selenium/playwright for UI testing.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.dashboard.data import CityMarketData, DashboardCache, DashboardDataProvider


class TestCityMarketData:
    """Tests for CityMarketData dataclass."""

    def test_city_market_data_creation(self) -> None:
        """Test creating city market data."""
        data = CityMarketData(
            city_code="NYC",
            city_name="New York City",
            current_temp=45.5,
            high_threshold=42,
            yes_bid=45,
            yes_ask=48,
            spread=3,
            volume=1000,
            open_interest=5000,
            last_signal="BUY",
            last_signal_time=datetime.now(timezone.utc),
        )

        assert data.city_code == "NYC"
        assert data.current_temp == 45.5
        assert data.spread == 3
        assert data.last_signal == "BUY"

    def test_city_market_data_optional_fields(self) -> None:
        """Test city market data with optional fields."""
        data = CityMarketData(
            city_code="LAX",
            city_name="Los Angeles",
        )

        assert data.current_temp is None
        assert data.yes_bid is None
        assert data.last_signal is None


class TestDashboardCache:
    """Tests for DashboardCache dataclass."""

    def test_cache_creation(self) -> None:
        """Test creating dashboard cache."""
        cache = DashboardCache(ttl_seconds=10)

        assert cache.ttl_seconds == 10
        assert cache.city_market_data == []
        assert cache.city_market_data_time is None

    def test_cache_default_ttl(self) -> None:
        """Test default TTL value."""
        cache = DashboardCache()

        assert cache.ttl_seconds == 5


class TestDashboardDataProvider:
    """Tests for DashboardDataProvider class."""

    @pytest.fixture
    def data_provider(self) -> DashboardDataProvider:
        """Create data provider instance."""
        return DashboardDataProvider(cache_ttl=5)

    def test_provider_initialization(self) -> None:
        """Test data provider initialization."""
        provider = DashboardDataProvider(cache_ttl=10)

        assert provider._cache.ttl_seconds == 10

    def test_get_city_codes(self, data_provider: DashboardDataProvider) -> None:
        """Test getting city codes."""
        with patch("src.dashboard.data.city_loader") as mock_loader:
            mock_loader.get_all_cities.return_value = {
                "NYC": {},
                "LAX": {},
                "CHI": {},
            }

            codes = data_provider.get_city_codes()

            assert len(codes) == 3
            assert "NYC" in codes

    def test_get_city_codes_fallback(self, data_provider: DashboardDataProvider) -> None:
        """Test city codes fallback on error."""
        with patch("src.dashboard.data.city_loader") as mock_loader:
            mock_loader.get_all_cities.side_effect = Exception("Config error")

            codes = data_provider.get_city_codes()

            # Should return fallback list
            assert len(codes) == 10
            assert "NYC" in codes

    def test_get_city_market_data(self, data_provider: DashboardDataProvider) -> None:
        """Test getting city market data."""
        with patch("src.dashboard.data.city_loader") as mock_loader:
            mock_loader.get_all_cities.return_value = {"NYC": {}, "LAX": {}}
            mock_city = MagicMock()
            mock_city.name = "New York"
            mock_loader.get_city.return_value = mock_city

            data = data_provider.get_city_market_data()

            assert len(data) >= 2
            assert all(isinstance(d, CityMarketData) for d in data)

    def test_get_city_market_data_cached(self, data_provider: DashboardDataProvider) -> None:
        """Test that city market data is cached."""
        with patch("src.dashboard.data.city_loader") as mock_loader:
            mock_loader.get_all_cities.return_value = {"NYC": {}}
            mock_city = MagicMock()
            mock_city.name = "New York"
            mock_loader.get_city.return_value = mock_city

            # First call
            data1 = data_provider.get_city_market_data()

            # Second call should return cached data
            data2 = data_provider.get_city_market_data()

            assert data1 == data2

    def test_get_equity_curve(self, data_provider: DashboardDataProvider) -> None:
        """Test getting equity curve data."""
        # Use dates that are on or after the launch date (Jan 31, 2026)
        launch_date = date(2026, 1, 31)
        start_date = launch_date
        end_date = date.today()

        curve = data_provider.get_equity_curve(start_date, end_date)

        # Curve length depends on days from launch to today
        expected_days = (end_date - start_date).days + 1
        assert len(curve) == expected_days
        assert all("ending_equity" in point for point in curve)
        assert all("daily_pnl" in point for point in curve)
        assert all("drawdown" in point for point in curve)

    def test_get_equity_curve_default_dates(self, data_provider: DashboardDataProvider) -> None:
        """Test equity curve with default date range."""
        curve = data_provider.get_equity_curve()

        assert len(curve) > 0
        assert "date" in curve[0]

    def test_get_city_metrics(self, data_provider: DashboardDataProvider) -> None:
        """Test getting city metrics."""
        with patch("src.dashboard.data.city_loader") as mock_loader:
            mock_loader.get_all_cities.return_value = {"NYC": {}, "LAX": {}}

            metrics = data_provider.get_city_metrics()

            assert len(metrics) >= 2
            assert all("city_code" in m for m in metrics)
            assert all("win_rate" in m for m in metrics)
            assert all("net_pnl" in m for m in metrics)

    def test_get_public_trades(self, data_provider: DashboardDataProvider) -> None:
        """Test getting public trades."""
        trades = data_provider.get_public_trades(limit=50)

        assert len(trades) <= 50
        assert all("ticker" in t for t in trades)
        assert all("trade_time" in t for t in trades)

        # Verify 60-minute delay
        now = datetime.now(timezone.utc)
        for trade in trades:
            trade_time = datetime.fromisoformat(trade["trade_time"].replace("Z", "+00:00"))
            assert (now - trade_time).total_seconds() >= 60 * 60  # At least 60 minutes old

    def test_get_public_trades_city_filter(self, data_provider: DashboardDataProvider) -> None:
        """Test filtering public trades by city."""
        trades = data_provider.get_public_trades(city_code="NYC", limit=100)

        # All trades should be for NYC
        assert all(t.get("city_code") == "NYC" for t in trades)

    def test_get_health_status(self, data_provider: DashboardDataProvider) -> None:
        """Test getting health status."""
        health = data_provider.get_health_status()

        assert "overall_status" in health
        assert health["overall_status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in health
        assert "summary" in health

    def test_get_health_status_components(self, data_provider: DashboardDataProvider) -> None:
        """Test health status has expected components."""
        health = data_provider.get_health_status()

        components = health.get("components", [])
        component_names = [c.get("name") for c in components]

        # Should have key components
        assert "Kalshi API" in component_names
        assert "Weather API (NWS)" in component_names
        assert "Dashboard" in component_names

    def test_cache_validity(self, data_provider: DashboardDataProvider) -> None:
        """Test cache validity checking."""
        # No cache time set
        assert not data_provider._is_cache_valid(None)

        # Recent cache
        recent_time = datetime.now(timezone.utc)
        assert data_provider._is_cache_valid(recent_time)

        # Expired cache
        old_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        assert not data_provider._is_cache_valid(old_time)


class TestDashboardDataProviderIntegration:
    """Integration tests for data provider with real city config."""

    @pytest.fixture
    def data_provider(self) -> DashboardDataProvider:
        """Create data provider instance."""
        return DashboardDataProvider(cache_ttl=5)

    def test_all_10_cities_have_data(self, data_provider: DashboardDataProvider) -> None:
        """Test that all 10 cities have market data."""
        data = data_provider.get_city_market_data()

        # Should have exactly 10 cities
        assert len(data) == 10

        # Each city should have required fields
        for city_data in data:
            assert city_data.city_code is not None
            assert city_data.city_name is not None

    def test_equity_curve_is_chronological(self, data_provider: DashboardDataProvider) -> None:
        """Test that equity curve points are in chronological order."""
        curve = data_provider.get_equity_curve()

        dates = [point["date"] for point in curve]
        assert dates == sorted(dates)

    def test_trades_are_sorted_by_time_descending(self, data_provider: DashboardDataProvider) -> None:
        """Test that trades are sorted by time descending."""
        trades = data_provider.get_public_trades(limit=50)

        times = [trade["trade_time"] for trade in trades]
        assert times == sorted(times, reverse=True)
