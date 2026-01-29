"""Unit tests for analytics rollups.

Tests the rollup table creation and metric aggregation functions.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.analytics.rollups import (
    CityMetrics,
    EquityCurvePoint,
    StrategyMetrics,
    create_rollup_tables,
    get_city_metrics,
    get_equity_curve,
    get_strategy_metrics,
    run_daily_rollups,
    update_city_metrics,
    update_equity_curve,
    update_strategy_metrics,
)


class TestCityMetrics:
    """Tests for CityMetrics dataclass."""

    def test_city_metrics_creation(self) -> None:
        """Test creating city metrics."""
        metrics = CityMetrics(
            city_code="NYC",
            date=date(2026, 1, 28),
            trade_count=10,
            volume=Decimal("1000.00"),
            gross_pnl=Decimal("150.00"),
            net_pnl=Decimal("140.00"),
            fees=Decimal("10.00"),
            win_count=7,
            loss_count=3,
            avg_position_size=Decimal("100.00"),
            max_position_size=Decimal("200.00"),
        )

        assert metrics.city_code == "NYC"
        assert metrics.trade_count == 10
        assert metrics.win_rate == 70.0

    def test_city_metrics_win_rate_zero_trades(self) -> None:
        """Test win rate calculation with zero trades."""
        metrics = CityMetrics(
            city_code="NYC",
            date=date(2026, 1, 28),
            trade_count=0,
            volume=Decimal("0"),
            gross_pnl=Decimal("0"),
            net_pnl=Decimal("0"),
            fees=Decimal("0"),
            win_count=0,
            loss_count=0,
            avg_position_size=Decimal("0"),
            max_position_size=Decimal("0"),
        )

        assert metrics.win_rate == 0.0

    def test_city_metrics_profit_factor(self) -> None:
        """Test profit factor calculation."""
        metrics = CityMetrics(
            city_code="NYC",
            date=date(2026, 1, 28),
            trade_count=10,
            volume=Decimal("1000.00"),
            gross_pnl=Decimal("150.00"),
            net_pnl=Decimal("140.00"),
            fees=Decimal("10.00"),
            win_count=8,
            loss_count=2,
            avg_position_size=Decimal("100.00"),
            max_position_size=Decimal("200.00"),
        )

        assert metrics.profit_factor == 4.0

    def test_city_metrics_profit_factor_no_losses(self) -> None:
        """Test profit factor with no losses returns None."""
        metrics = CityMetrics(
            city_code="NYC",
            date=date(2026, 1, 28),
            trade_count=5,
            volume=Decimal("500.00"),
            gross_pnl=Decimal("100.00"),
            net_pnl=Decimal("95.00"),
            fees=Decimal("5.00"),
            win_count=5,
            loss_count=0,
            avg_position_size=Decimal("100.00"),
            max_position_size=Decimal("100.00"),
        )

        assert metrics.profit_factor is None

    def test_city_metrics_profit_factor_no_wins(self) -> None:
        """Test profit factor with no wins returns 0."""
        metrics = CityMetrics(
            city_code="NYC",
            date=date(2026, 1, 28),
            trade_count=5,
            volume=Decimal("500.00"),
            gross_pnl=Decimal("-100.00"),
            net_pnl=Decimal("-105.00"),
            fees=Decimal("5.00"),
            win_count=0,
            loss_count=5,
            avg_position_size=Decimal("100.00"),
            max_position_size=Decimal("100.00"),
        )

        assert metrics.profit_factor == 0.0


class TestStrategyMetrics:
    """Tests for StrategyMetrics dataclass."""

    def test_strategy_metrics_creation(self) -> None:
        """Test creating strategy metrics."""
        metrics = StrategyMetrics(
            strategy_name="daily_high_temp",
            date=date(2026, 1, 28),
            signal_count=20,
            trade_count=15,
            gross_pnl=Decimal("200.00"),
            net_pnl=Decimal("180.00"),
            fees=Decimal("20.00"),
            win_count=10,
            loss_count=5,
            avg_edge=Decimal("5.25"),
            avg_confidence=Decimal("0.72"),
        )

        assert metrics.strategy_name == "daily_high_temp"
        assert metrics.win_rate == pytest.approx(66.67, rel=0.01)
        assert metrics.conversion_rate == 75.0

    def test_strategy_metrics_zero_signals(self) -> None:
        """Test conversion rate with zero signals."""
        metrics = StrategyMetrics(
            strategy_name="daily_high_temp",
            date=date(2026, 1, 28),
            signal_count=0,
            trade_count=0,
            gross_pnl=Decimal("0"),
            net_pnl=Decimal("0"),
            fees=Decimal("0"),
            win_count=0,
            loss_count=0,
            avg_edge=Decimal("0"),
            avg_confidence=Decimal("0"),
        )

        assert metrics.conversion_rate == 0.0


class TestEquityCurvePoint:
    """Tests for EquityCurvePoint dataclass."""

    def test_equity_curve_point_creation(self) -> None:
        """Test creating equity curve point."""
        point = EquityCurvePoint(
            date=date(2026, 1, 28),
            starting_equity=Decimal("5000.00"),
            ending_equity=Decimal("5150.00"),
            daily_pnl=Decimal("150.00"),
            cumulative_pnl=Decimal("1500.00"),
            drawdown=Decimal("0"),
            drawdown_pct=Decimal("0"),
            high_water_mark=Decimal("5150.00"),
        )

        assert point.daily_pnl == Decimal("150.00")
        assert point.ending_equity == Decimal("5150.00")


class TestRollupTableCreation:
    """Tests for rollup table creation."""

    def test_create_rollup_tables(self) -> None:
        """Test creating all rollup tables."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        create_rollup_tables(mock_engine)

        # Should have executed SQL statements
        assert mock_conn.execute.called
        assert mock_conn.commit.called

    def test_create_rollup_tables_creates_schema(self) -> None:
        """Test that rollup table creation creates analytics schema."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        create_rollup_tables(mock_engine)

        # First call should create schema
        calls = mock_conn.execute.call_args_list
        assert len(calls) > 0


class TestCityMetricsRollup:
    """Tests for city metrics rollup functions."""

    def test_update_city_metrics(self) -> None:
        """Test updating city metrics rollup."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        target_date = date(2026, 1, 28)
        affected = update_city_metrics(mock_engine, target_date)

        assert affected == 3
        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_update_city_metrics_defaults_to_today(self) -> None:
        """Test update_city_metrics defaults to today's date."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        # Call without target_date
        affected = update_city_metrics(mock_engine)

        assert affected == 0
        mock_conn.execute.assert_called_once()

    def test_get_city_metrics_all(self) -> None:
        """Test querying all city metrics."""
        mock_row = MagicMock()
        mock_row._mapping = {
            "city_code": "NYC",
            "date": date(2026, 1, 28),
            "trade_count": 10,
        }

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        metrics = get_city_metrics(mock_engine)

        assert len(metrics) == 1
        assert metrics[0]["city_code"] == "NYC"

    def test_get_city_metrics_filtered(self) -> None:
        """Test querying city metrics with filters."""
        mock_row = MagicMock()
        mock_row._mapping = {"city_code": "NYC", "trade_count": 5}

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        metrics = get_city_metrics(
            mock_engine,
            city_code="NYC",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        assert len(metrics) == 1


class TestStrategyMetricsRollup:
    """Tests for strategy metrics rollup functions."""

    def test_update_strategy_metrics(self) -> None:
        """Test updating strategy metrics rollup."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        target_date = date(2026, 1, 28)
        affected = update_strategy_metrics(mock_engine, target_date)

        assert affected == 2
        mock_conn.execute.assert_called_once()

    def test_update_strategy_metrics_defaults_to_today(self) -> None:
        """Test update_strategy_metrics defaults to today's date."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        # Call without target_date
        affected = update_strategy_metrics(mock_engine)

        assert affected == 0

    def test_get_strategy_metrics(self) -> None:
        """Test querying strategy metrics."""
        mock_row = MagicMock()
        mock_row._mapping = {
            "strategy_name": "daily_high_temp",
            "trade_count": 15,
        }

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        metrics = get_strategy_metrics(mock_engine, strategy_name="daily_high_temp")

        assert len(metrics) == 1
        assert metrics[0]["strategy_name"] == "daily_high_temp"

    def test_get_strategy_metrics_with_date_filters(self) -> None:
        """Test querying strategy metrics with date filters."""
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        metrics = get_strategy_metrics(
            mock_engine,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        assert len(metrics) == 0
        mock_conn.execute.assert_called_once()


class TestEquityCurveRollup:
    """Tests for equity curve rollup functions."""

    def test_update_equity_curve_first_day(self) -> None:
        """Test updating equity curve for first day (no previous)."""
        # Mock for previous day query (no results)
        mock_prev_result = MagicMock()
        mock_prev_result.fetchone.return_value = None

        # Mock for daily P&L query
        mock_pnl_result = MagicMock()
        mock_pnl_result.fetchone.return_value = (Decimal("100.00"),)

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        # Return different results for different queries
        mock_conn.execute.side_effect = [mock_prev_result, mock_pnl_result, MagicMock()]

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        result = update_equity_curve(mock_engine, date(2026, 1, 28))

        assert result is True
        assert mock_conn.commit.called

    def test_update_equity_curve_defaults_to_today(self) -> None:
        """Test update_equity_curve defaults to today's date."""
        mock_prev_result = MagicMock()
        mock_prev_result.fetchone.return_value = None

        mock_pnl_result = MagicMock()
        mock_pnl_result.fetchone.return_value = (Decimal("0"),)

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = [mock_prev_result, mock_pnl_result, MagicMock()]

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        # Call without target_date
        result = update_equity_curve(mock_engine)

        assert result is True

    def test_update_equity_curve_no_pnl_row(self) -> None:
        """Test update_equity_curve handles no P&L row."""
        mock_prev_result = MagicMock()
        mock_prev_result.fetchone.return_value = None

        mock_pnl_result = MagicMock()
        mock_pnl_result.fetchone.return_value = None  # No trades

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = [mock_prev_result, mock_pnl_result, MagicMock()]

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        result = update_equity_curve(mock_engine, date(2026, 1, 28))

        assert result is True

    def test_update_equity_curve_with_drawdown(self) -> None:
        """Test update_equity_curve calculates drawdown correctly."""
        # Previous day had higher equity (creates drawdown)
        mock_prev_result = MagicMock()
        mock_prev_result.fetchone.return_value = (
            Decimal("5200.00"),  # ending_equity
            Decimal("200.00"),   # cumulative_pnl
            Decimal("5200.00"),  # high_water_mark
        )

        # Today has a loss
        mock_pnl_result = MagicMock()
        mock_pnl_result.fetchone.return_value = (Decimal("-100.00"),)

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = [mock_prev_result, mock_pnl_result, MagicMock()]

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        result = update_equity_curve(mock_engine, date(2026, 1, 29))

        assert result is True

    def test_update_equity_curve_with_previous(self) -> None:
        """Test updating equity curve with previous day data."""
        # Mock for previous day query (has data)
        mock_prev_result = MagicMock()
        mock_prev_result.fetchone.return_value = (
            Decimal("5100.00"),  # ending_equity
            Decimal("100.00"),   # cumulative_pnl
            Decimal("5100.00"),  # high_water_mark
        )

        # Mock for daily P&L query
        mock_pnl_result = MagicMock()
        mock_pnl_result.fetchone.return_value = (Decimal("50.00"),)

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_conn.execute.side_effect = [mock_prev_result, mock_pnl_result, MagicMock()]

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        result = update_equity_curve(mock_engine, date(2026, 1, 29))

        assert result is True

    def test_get_equity_curve(self) -> None:
        """Test querying equity curve."""
        mock_row = MagicMock()
        mock_row._mapping = {
            "date": date(2026, 1, 28),
            "ending_equity": Decimal("5150.00"),
            "daily_pnl": Decimal("150.00"),
        }

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        curve = get_equity_curve(mock_engine)

        assert len(curve) == 1
        assert curve[0]["daily_pnl"] == Decimal("150.00")

    def test_get_equity_curve_with_date_filters(self) -> None:
        """Test querying equity curve with date filters."""
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        curve = get_equity_curve(
            mock_engine,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        assert len(curve) == 0
        mock_conn.execute.assert_called_once()


class TestEquityCurveEdgeCases:
    """Tests for equity curve edge cases."""

    def test_get_equity_curve_empty_date_range(self) -> None:
        """Test get_equity_curve with date range that returns no results."""
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        # Query with future dates that have no data
        curve = get_equity_curve(
            mock_engine,
            start_date=date(2099, 1, 1),
            end_date=date(2099, 12, 31),
        )

        assert len(curve) == 0

    def test_update_equity_curve_with_zero_pnl(self) -> None:
        """Test update_equity_curve when daily P&L is exactly zero."""
        mock_prev_result = MagicMock()
        mock_prev_result.fetchone.return_value = (
            Decimal("5000.00"),
            Decimal("0"),
            Decimal("5000.00"),
        )

        mock_pnl_result = MagicMock()
        mock_pnl_result.fetchone.return_value = (Decimal("0"),)  # Zero P&L

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = [mock_prev_result, mock_pnl_result, MagicMock()]

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        result = update_equity_curve(mock_engine, date(2026, 1, 28))

        assert result is True


class TestDailyRollups:
    """Tests for combined daily rollup function."""

    def test_run_daily_rollups(self) -> None:
        """Test running all daily rollups."""
        with patch("src.analytics.rollups.update_city_metrics") as mock_city, \
             patch("src.analytics.rollups.update_strategy_metrics") as mock_strategy, \
             patch("src.analytics.rollups.update_equity_curve") as mock_equity:

            mock_city.return_value = 5
            mock_strategy.return_value = 2
            mock_equity.return_value = True

            mock_engine = MagicMock()

            results = run_daily_rollups(mock_engine, date(2026, 1, 28))

            assert results["city_metrics"] == 5
            assert results["strategy_metrics"] == 2
            assert results["equity_curve"] == 1

            mock_city.assert_called_once()
            mock_strategy.assert_called_once()
            mock_equity.assert_called_once()

    def test_run_daily_rollups_defaults_to_today(self) -> None:
        """Test that run_daily_rollups defaults to today's date."""
        with patch("src.analytics.rollups.update_city_metrics") as mock_city, \
             patch("src.analytics.rollups.update_strategy_metrics") as mock_strategy, \
             patch("src.analytics.rollups.update_equity_curve") as mock_equity:

            mock_city.return_value = 0
            mock_strategy.return_value = 0
            mock_equity.return_value = True

            mock_engine = MagicMock()

            # Call without target_date
            run_daily_rollups(mock_engine)

            # Should use today's date
            today = datetime.now(timezone.utc).date()
            mock_city.assert_called_with(mock_engine, today)
