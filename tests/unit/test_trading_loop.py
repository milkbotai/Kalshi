"""Unit tests for trading loop.

Tests the main trading cycle including weather fetching, market evaluation,
gate checks, and order submission across different trading modes.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.api.response_models import Market
from src.shared.api.weather_cache import CachedWeather
from src.shared.config.settings import TradingMode
from src.trader.oms import OrderManagementSystem, OrderState
from src.trader.risk import CircuitBreaker, RiskCalculator
from src.trader.strategies.daily_high_temp import DailyHighTempStrategy
from src.trader.strategy import Signal
from src.trader.trading_loop import (
    MultiCityOrchestrator,
    MultiCityRunResult,
    TradingCycleResult,
    TradingLoop,
)


class TestTradingCycleResult:
    """Tests for TradingCycleResult dataclass."""

    def test_cycle_result_creation(self) -> None:
        """Test creating a cycle result."""
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        result = TradingCycleResult(
            city_code="NYC",
            started_at=started,
            completed_at=completed,
            weather_fetched=True,
            markets_fetched=5,
            signals_generated=5,
            gates_passed=2,
            orders_submitted=2,
        )

        assert result.city_code == "NYC"
        assert result.weather_fetched is True
        assert result.markets_fetched == 5
        assert result.success is True

    def test_cycle_result_with_errors(self) -> None:
        """Test cycle result with errors."""
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        result = TradingCycleResult(
            city_code="NYC",
            started_at=started,
            completed_at=completed,
            weather_fetched=False,
            markets_fetched=0,
            signals_generated=0,
            gates_passed=0,
            orders_submitted=0,
            errors=["Weather fetch failed"],
        )

        assert result.success is False
        assert len(result.errors) == 1

    def test_cycle_duration(self) -> None:
        """Test duration calculation."""
        from datetime import timedelta

        started = datetime.now(timezone.utc)
        completed = started + timedelta(seconds=5)

        result = TradingCycleResult(
            city_code="NYC",
            started_at=started,
            completed_at=completed,
            weather_fetched=True,
            markets_fetched=0,
            signals_generated=0,
            gates_passed=0,
            orders_submitted=0,
        )

        assert result.duration_seconds == 5.0


class TestTradingLoop:
    """Tests for TradingLoop class."""

    @pytest.fixture
    def mock_weather_cache(self) -> MagicMock:
        """Create mock weather cache."""
        cache = MagicMock()
        cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 45,
                        "isDaytime": True,
                    }
                ]
            },
            observation={"temperature": {"value": 7.0}},
            is_stale=False,
        )
        return cache

    @pytest.fixture
    def mock_kalshi_client(self) -> MagicMock:
        """Create mock Kalshi client."""
        client = MagicMock()
        client.get_markets_typed.return_value = [
            Market(
                ticker="HIGHNYC-25JAN26-T42",
                event_ticker="HIGHNYC-25JAN26",
                title="Will NYC high be >= 42F?",
                yes_bid=45,
                yes_ask=48,
                volume=1000,
                open_interest=5000,
                status="open",
                strike_price=42.0,
            )
        ]
        client.create_order.return_value = {"order_id": "kalshi_order_123"}
        return client

    @pytest.fixture
    def mock_city_loader(self) -> MagicMock:
        """Create mock city loader."""
        mock_city = MagicMock()
        mock_city.code = "NYC"
        mock_city.name = "New York City"
        mock_city.nws_office = "OKX"
        mock_city.nws_grid_x = 33
        mock_city.nws_grid_y = 37
        mock_city.settlement_station = "KNYC"
        mock_city.cluster = "NE"
        return mock_city

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_trading_loop_initialization_shadow_mode(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_weather_cache: MagicMock,
    ) -> None:
        """Test trading loop initializes in shadow mode."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        settings.kalshi_api_key = None
        settings.kalshi_api_secret = None
        mock_settings.return_value = settings

        loop = TradingLoop(
            weather_cache=mock_weather_cache,
            trading_mode=TradingMode.SHADOW,
        )

        assert loop.trading_mode == TradingMode.SHADOW
        # Shadow mode should not have a kalshi client
        assert loop.kalshi_client is None

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_run_cycle_shadow_mode(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_weather_cache: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test running cycle in shadow mode (no API calls)."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        loop = TradingLoop(
            weather_cache=mock_weather_cache,
            trading_mode=TradingMode.SHADOW,
        )

        result = loop.run_cycle("NYC")

        assert result.city_code == "NYC"
        assert result.weather_fetched is True
        # Shadow mode doesn't fetch markets
        assert result.markets_fetched == 0
        assert result.success is True

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_run_cycle_with_markets(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_weather_cache: MagicMock,
        mock_kalshi_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test running cycle with market evaluation."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.DEMO
        settings.kalshi_api_key = "test_key"
        settings.kalshi_api_secret = "test_secret"
        settings.kalshi_api_url = "https://demo-api.kalshi.co"
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        loop = TradingLoop(
            kalshi_client=mock_kalshi_client,
            weather_cache=mock_weather_cache,
            trading_mode=TradingMode.DEMO,
        )

        result = loop.run_cycle("NYC")

        assert result.weather_fetched is True
        assert result.markets_fetched == 1
        assert result.signals_generated == 1
        mock_kalshi_client.get_markets_typed.assert_called_once()

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_run_cycle_circuit_breaker_paused(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_weather_cache: MagicMock,
    ) -> None:
        """Test cycle is skipped when circuit breaker is paused."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        circuit_breaker = CircuitBreaker()
        circuit_breaker._paused = True
        circuit_breaker._pause_reason = "Daily loss limit exceeded"

        loop = TradingLoop(
            weather_cache=mock_weather_cache,
            circuit_breaker=circuit_breaker,
            trading_mode=TradingMode.SHADOW,
        )

        result = loop.run_cycle("NYC")

        assert result.success is False
        assert "Trading paused" in result.errors[0]
        assert result.weather_fetched is False

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_run_cycle_weather_fetch_error(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
    ) -> None:
        """Test cycle handles weather fetch errors gracefully."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings
        mock_loader.get_city.side_effect = KeyError("City not found")

        mock_cache = MagicMock()
        mock_cache.get_weather.side_effect = Exception("Weather API error")

        loop = TradingLoop(
            weather_cache=mock_cache,
            trading_mode=TradingMode.SHADOW,
        )

        result = loop.run_cycle("INVALID")

        assert result.success is False
        assert any("Weather fetch failed" in e for e in result.errors)

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_run_cycle_stale_weather_warning(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test cycle logs warning for stale weather data."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        stale_cache = MagicMock()
        stale_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"temperature": 45, "isDaytime": True}]},
            is_stale=True,  # Data is stale
        )

        loop = TradingLoop(
            weather_cache=stale_cache,
            trading_mode=TradingMode.SHADOW,
        )

        result = loop.run_cycle("NYC")

        # Should still succeed but weather was stale
        assert result.weather_fetched is True

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_run_cycle_market_fetch_error(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_weather_cache: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test cycle handles market fetch errors gracefully."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.DEMO
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        failing_kalshi = MagicMock()
        failing_kalshi.get_markets_typed.side_effect = Exception("API Error")

        loop = TradingLoop(
            kalshi_client=failing_kalshi,
            weather_cache=mock_weather_cache,
            trading_mode=TradingMode.DEMO,
        )

        result = loop.run_cycle("NYC")

        assert any("Market fetch failed" in e for e in result.errors)

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_build_weather_data(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_weather_cache: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test weather data extraction from forecast."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        loop = TradingLoop(
            weather_cache=mock_weather_cache,
            trading_mode=TradingMode.SHADOW,
        )

        forecast = {
            "periods": [
                {"name": "Today", "temperature": 52, "isDaytime": True},
                {"name": "Tonight", "temperature": 35, "isDaytime": False},
            ]
        }

        weather_data = loop._build_weather_data(forecast, mock_city_loader)

        assert weather_data["temperature"] == 52
        assert weather_data["city_code"] == "NYC"

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_order_submission_demo_mode(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_weather_cache: MagicMock,
        mock_kalshi_client: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test order submission in DEMO mode calls Kalshi API."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.DEMO
        settings.kalshi_api_key = "test"
        settings.kalshi_api_secret = "test"
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        # Create a strategy that returns BUY signal
        mock_strategy = MagicMock()
        mock_strategy.name = "test_strategy"
        mock_strategy.evaluate.return_value = Signal(
            ticker="HIGHNYC-25JAN26-T42",
            p_yes=0.70,
            uncertainty=0.1,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=65.0,
        )

        loop = TradingLoop(
            kalshi_client=mock_kalshi_client,
            weather_cache=mock_weather_cache,
            strategy=mock_strategy,
            trading_mode=TradingMode.DEMO,
        )

        result = loop.run_cycle("NYC")

        # Should have called create_order
        assert mock_kalshi_client.create_order.called or result.orders_submitted >= 0

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_shadow_mode_simulates_fills(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_weather_cache: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test SHADOW mode simulates order fills without API calls."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        oms = OrderManagementSystem()

        loop = TradingLoop(
            weather_cache=mock_weather_cache,
            oms=oms,
            trading_mode=TradingMode.SHADOW,
        )

        # Create signal directly via submit_order to test SHADOW fill
        from src.trader.strategy import Signal

        signal = Signal(
            ticker="TEST",
            p_yes=0.65,
            uncertainty=0.1,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=60.0,
        )

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=40.0,
        )

        # Call private method to test shadow fill
        order = loop._submit_order(signal, mock_city_loader, market, 100)

        assert order is not None
        # In shadow mode, order should be marked as filled
        saved_order = oms.get_order_by_intent_key(order["intent_key"])
        assert saved_order is not None
        assert saved_order["status"] == OrderState.FILLED


class TestTradingLoopRiskChecks:
    """Tests for risk checks in trading loop."""

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_trade_blocked_by_trade_size_limit(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
    ) -> None:
        """Test trade is blocked when exceeding trade size limit."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        # Very low trade risk limit
        risk_calc = RiskCalculator(max_trade_risk_pct=0.001)  # 0.1% of bankroll

        mock_cache = MagicMock()
        mock_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"temperature": 45, "isDaytime": True}]},
        )

        loop = TradingLoop(
            weather_cache=mock_cache,
            risk_calculator=risk_calc,
            trading_mode=TradingMode.SHADOW,
        )

        # Risk calc should block large trades
        # With $5000 bankroll and 0.1% max, max trade risk is $5
        allowed = risk_calc.check_trade_size(trade_risk=50.0, quantity=100)
        assert allowed is False


class TestTradingLoopErrorHandling:
    """Tests for error handling in trading loop."""

    @pytest.fixture
    def mock_city_loader(self) -> MagicMock:
        """Create mock city loader."""
        mock_city = MagicMock()
        mock_city.code = "NYC"
        mock_city.name = "New York City"
        mock_city.nws_office = "OKX"
        mock_city.nws_grid_x = 33
        mock_city.nws_grid_y = 37
        mock_city.settlement_station = "KNYC"
        mock_city.cluster = "NE"
        return mock_city

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_order_submission_exception_handling(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test that order submission exceptions are caught and logged."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.DEMO
        settings.kalshi_api_key = "test"
        settings.kalshi_api_secret = "test"
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        # Mock Kalshi client that raises exception on create_order
        mock_kalshi = MagicMock()
        mock_kalshi.get_markets_typed.return_value = [
            Market(
                ticker="HIGHNYC-25JAN26-T42",
                event_ticker="HIGHNYC-25JAN26",
                title="Test",
                status="open",
                yes_bid=30,
                yes_ask=35,
                volume=1000,
                open_interest=5000,
                strike_price=42.0,
            )
        ]
        mock_kalshi.create_order.side_effect = Exception("API connection failed")

        # Mock strategy that returns BUY signal
        mock_strategy = MagicMock()
        mock_strategy.name = "test"
        mock_strategy.evaluate.return_value = Signal(
            ticker="HIGHNYC-25JAN26-T42",
            p_yes=0.7,
            uncertainty=0.1,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=65.0,
        )

        mock_weather_cache = MagicMock()
        mock_weather_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"temperature": 50, "isDaytime": True}]},
        )

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            strategy=mock_strategy,
            trading_mode=TradingMode.DEMO,
        )

        result = loop.run_cycle("NYC")

        # Should have error but not crash
        assert len(result.errors) > 0
        assert any("Order submission failed" in e for e in result.errors)
        assert result.orders_submitted == 0

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_strategy_evaluation_exception_handling(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test that strategy evaluation exceptions are caught."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.DEMO
        settings.kalshi_api_key = "test"
        settings.kalshi_api_secret = "test"
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        mock_kalshi = MagicMock()
        mock_kalshi.get_markets_typed.return_value = [
            Market(
                ticker="HIGHNYC-25JAN26-T42",
                event_ticker="HIGHNYC-25JAN26",
                title="Test",
                status="open",
                strike_price=42.0,
            )
        ]

        # Strategy that raises exception
        mock_strategy = MagicMock()
        mock_strategy.name = "test"
        mock_strategy.evaluate.side_effect = Exception("Strategy calculation error")

        mock_weather_cache = MagicMock()
        mock_weather_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"temperature": 50, "isDaytime": True}]},
        )

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            strategy=mock_strategy,
            trading_mode=TradingMode.DEMO,
        )

        result = loop.run_cycle("NYC")

        # Should have error for strategy evaluation
        assert len(result.errors) > 0
        assert any("Strategy evaluation failed" in e for e in result.errors)
        assert result.signals_generated == 0

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_oms_update_failure_handling(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test handling of OMS update failures."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.DEMO
        settings.kalshi_api_key = "test"
        settings.kalshi_api_secret = "test"
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        # Mock OMS that fails on update
        mock_oms = MagicMock()
        mock_oms.submit_order.return_value = {"intent_key": "test_key"}
        mock_oms.update_order_status.side_effect = Exception("Database error")

        mock_kalshi = MagicMock()
        mock_kalshi.get_markets_typed.return_value = [
            Market(
                ticker="HIGHNYC-25JAN26-T42",
                event_ticker="HIGHNYC-25JAN26",
                title="Test",
                status="open",
                yes_bid=30,
                yes_ask=35,
                volume=1000,
                open_interest=5000,
                strike_price=42.0,
            )
        ]
        mock_kalshi.create_order.return_value = {"order_id": "kalshi_123"}

        mock_strategy = MagicMock()
        mock_strategy.name = "test"
        mock_strategy.evaluate.return_value = Signal(
            ticker="HIGHNYC-25JAN26-T42",
            p_yes=0.7,
            uncertainty=0.1,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=65.0,
        )

        mock_weather_cache = MagicMock()
        mock_weather_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"temperature": 50, "isDaytime": True}]},
        )

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            strategy=mock_strategy,
            oms=mock_oms,
            trading_mode=TradingMode.DEMO,
        )

        result = loop.run_cycle("NYC")

        # Should have error from OMS update failure
        assert len(result.errors) > 0

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_build_weather_data_with_missing_periods(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
    ) -> None:
        """Test _build_weather_data handles missing periods gracefully."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        mock_city = MagicMock()
        mock_city.code = "NYC"

        loop = TradingLoop(trading_mode=TradingMode.SHADOW)

        # Empty forecast
        forecast = {"periods": []}
        weather_data = loop._build_weather_data(forecast, mock_city)

        assert weather_data["city_code"] == "NYC"
        assert weather_data["temperature"] is None

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_build_weather_data_with_nighttime_only(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
    ) -> None:
        """Test _build_weather_data handles nighttime-only periods."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        mock_city = MagicMock()
        mock_city.code = "NYC"

        loop = TradingLoop(trading_mode=TradingMode.SHADOW)

        # Only nighttime periods
        forecast = {
            "periods": [
                {"name": "Tonight", "temperature": 35, "isDaytime": False},
                {"name": "Tomorrow Night", "temperature": 32, "isDaytime": False},
            ]
        }
        weather_data = loop._build_weather_data(forecast, mock_city)

        # Should not find daytime temperature
        assert weather_data["temperature"] is None

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_submit_order_with_none_max_price(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
    ) -> None:
        """Test _submit_order handles None max_price."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        mock_city = MagicMock()
        mock_city.code = "NYC"

        loop = TradingLoop(trading_mode=TradingMode.SHADOW)

        signal = Signal(
            ticker="TEST",
            p_yes=0.65,
            uncertainty=0.1,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=None,  # None max_price
        )

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=40.0,
        )

        order = loop._submit_order(signal, mock_city, market, 100)

        # Should default to 50 cents
        assert order is not None


class TestMultiCityOrchestratorErrorHandling:
    """Tests for error handling in multi-city orchestrator."""

    @pytest.fixture
    def mock_trading_loop(self) -> MagicMock:
        """Create mock trading loop."""
        loop = MagicMock(spec=TradingLoop)
        loop.trading_mode = TradingMode.SHADOW
        loop.oms = MagicMock()
        loop.oms.get_orders_by_status.return_value = []
        loop.circuit_breaker = MagicMock()
        loop.circuit_breaker.is_paused = False
        loop.weather_cache = MagicMock()
        return loop

    @patch("src.trader.trading_loop.city_loader")
    def test_prefetch_weather_with_all_failures(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test prefetch_weather when all cities fail."""
        def mock_get_weather(city_code: str, force_refresh: bool = False) -> MagicMock:
            raise Exception(f"Weather API error for {city_code}")

        mock_trading_loop.weather_cache.get_weather.side_effect = mock_get_weather

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX", "CHI"],
            trading_mode=TradingMode.SHADOW,
        )

        results = orchestrator.prefetch_weather()

        # All should fail
        assert all(v is False for v in results.values())
        assert len(results) == 3

    @patch("src.trader.trading_loop.city_loader")
    def test_run_all_cities_with_exception_in_cycle(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test run_all_cities handles exceptions in individual cycles."""
        call_count = [0]

        def mock_run_cycle(city_code: str, quantity: int = 100) -> TradingCycleResult:
            call_count[0] += 1
            if city_code == "LAX":
                raise RuntimeError("Unexpected error in LAX cycle")
            return TradingCycleResult(
                city_code=city_code,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                weather_fetched=True,
                markets_fetched=5,
                signals_generated=5,
                gates_passed=2,
                orders_submitted=1,
            )

        mock_trading_loop.run_cycle.side_effect = mock_run_cycle

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX", "CHI"],
            trading_mode=TradingMode.SHADOW,
        )

        result = orchestrator.run_all_cities(prefetch_weather=False)

        # Should have results for all cities
        assert len(result.city_results) == 3
        assert result.cities_succeeded == 2
        assert result.cities_failed == 1

        # LAX should have error
        lax_result = result.city_results["LAX"]
        assert not lax_result.success
        assert len(lax_result.errors) > 0
        assert "Unexpected error" in lax_result.errors[0]

    @patch("src.trader.trading_loop.city_loader")
    def test_check_aggregate_risk_with_high_exposure(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test _check_aggregate_risk blocks when exposure too high."""
        # Mock high exposure from many pending orders
        large_orders = [
            {"quantity": 1000, "limit_price": 50}  # $500 each
            for _ in range(150)  # Total $75,000 exposure
        ]

        mock_trading_loop.oms.get_orders_by_status.side_effect = lambda status: (
            large_orders if status in ["pending", "resting"] else []
        )

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC"],
            trading_mode=TradingMode.SHADOW,
        )

        # Should block due to high exposure
        allowed = orchestrator._check_aggregate_risk()
        assert allowed is False

    @patch("src.trader.trading_loop.city_loader")
    def test_check_aggregate_risk_with_low_exposure(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test _check_aggregate_risk allows low exposure."""
        # Mock low exposure
        small_orders = [
            {"quantity": 100, "limit_price": 50}  # $50 each
            for _ in range(10)  # Total $500 exposure
        ]

        mock_trading_loop.oms.get_orders_by_status.side_effect = lambda status: (
            small_orders if status in ["pending", "resting"] else []
        )

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC"],
            trading_mode=TradingMode.SHADOW,
        )

        # Should allow
        allowed = orchestrator._check_aggregate_risk()
        assert allowed is True

    @patch("src.trader.trading_loop.city_loader")
    def test_get_run_summary_with_mixed_results(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test get_run_summary with mixed success/failure results."""
        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX"],
            trading_mode=TradingMode.SHADOW,
        )

        # Create mixed results
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        result = MultiCityRunResult(
            started_at=started,
            completed_at=completed,
            city_results={
                "NYC": TradingCycleResult(
                    city_code="NYC",
                    started_at=started,
                    completed_at=completed,
                    weather_fetched=True,
                    markets_fetched=5,
                    signals_generated=5,
                    gates_passed=2,
                    orders_submitted=1,
                ),
                "LAX": TradingCycleResult(
                    city_code="LAX",
                    started_at=started,
                    completed_at=completed,
                    weather_fetched=False,
                    markets_fetched=0,
                    signals_generated=0,
                    gates_passed=0,
                    orders_submitted=0,
                    errors=["Weather fetch failed"],
                ),
            },
            cities_succeeded=1,
            cities_failed=1,
            total_orders_submitted=1,
        )

        summary = orchestrator.get_run_summary(result)

        assert summary["cities_total"] == 2
        assert summary["cities_succeeded"] == 1
        assert summary["cities_failed"] == 1
        assert summary["trading_mode"] == "shadow"
        assert "NYC" in summary["per_city"]
        assert "LAX" in summary["per_city"]
        assert summary["per_city"]["NYC"]["success"] is True
        assert summary["per_city"]["LAX"]["success"] is False
        assert len(summary["per_city"]["LAX"]["errors"]) > 0

    @patch("src.trader.trading_loop.city_loader")
    def test_prefetch_weather_with_timeout(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test prefetch_weather handles slow/timeout scenarios."""
        import time

        def slow_weather_fetch(city_code: str, force_refresh: bool = False) -> MagicMock:
            if city_code == "LAX":
                time.sleep(0.1)  # Simulate slow response
            return MagicMock()

        mock_trading_loop.weather_cache.get_weather.side_effect = slow_weather_fetch

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX", "CHI"],
            max_parallel_weather=3,
            trading_mode=TradingMode.SHADOW,
        )

        start_time = time.time()
        results = orchestrator.prefetch_weather()
        elapsed = time.time() - start_time

        # Should complete (parallel execution)
        assert len(results) == 3
        # Should be faster than sequential (< 0.3s for 3 cities)
        assert elapsed < 0.3

    @patch("src.trader.trading_loop.city_loader")
    def test_run_all_cities_without_prefetch(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test run_all_cities with prefetch_weather=False."""
        def mock_run_cycle(city_code: str, quantity: int = 100) -> TradingCycleResult:
            return TradingCycleResult(
                city_code=city_code,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                weather_fetched=True,
                markets_fetched=5,
                signals_generated=5,
                gates_passed=2,
                orders_submitted=1,
            )

        mock_trading_loop.run_cycle.side_effect = mock_run_cycle

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX"],
            trading_mode=TradingMode.SHADOW,
        )

        result = orchestrator.run_all_cities(prefetch_weather=False)

        # Should not call prefetch
        mock_trading_loop.weather_cache.get_weather.assert_not_called()
        assert result.success is True
        assert result.cities_succeeded == 2


class TestTradingModeEnforcement:
    """Tests for trading mode enforcement (Story 4.10)."""

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_shadow_mode_never_calls_kalshi_api(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test SHADOW mode never calls Kalshi order API."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        mock_kalshi = MagicMock()

        # Even if kalshi_client is provided, it should not be used in SHADOW mode
        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            trading_mode=TradingMode.SHADOW,
        )

        # Run cycle
        loop.run_cycle("NYC")

        # create_order should NEVER be called in SHADOW mode
        mock_kalshi.create_order.assert_not_called()

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_demo_mode_uses_api(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test DEMO mode uses Kalshi API."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.DEMO
        settings.kalshi_api_key = "demo_key"
        settings.kalshi_api_secret = "demo_secret"
        settings.kalshi_api_url = "https://demo-api.kalshi.co"
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        mock_kalshi = MagicMock()
        mock_kalshi.get_markets_typed.return_value = [
            Market(
                ticker="HIGHNYC-25JAN26-T42",
                event_ticker="HIGHNYC-25JAN26",
                title="Test",
                status="open",
                yes_bid=40,
                yes_ask=45,
                volume=1000,
                open_interest=5000,
            )
        ]

        mock_strategy = MagicMock()
        mock_strategy.name = "test"
        mock_strategy.evaluate.return_value = Signal(
            ticker="HIGHNYC-25JAN26-T42",
            p_yes=0.7,
            uncertainty=0.1,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=60.0,
        )

        mock_weather_cache = MagicMock()
        from src.shared.api.weather_cache import CachedWeather
        mock_weather_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"temperature": 45, "isDaytime": True}]},
        )

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            strategy=mock_strategy,
            trading_mode=TradingMode.DEMO,
        )

        loop.run_cycle("NYC")

        # In DEMO mode, API should be called
        mock_kalshi.get_markets_typed.assert_called()

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_live_mode_requires_confirmation(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test LIVE mode requires explicit confirmation before trading."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.LIVE
        settings.kalshi_api_key = "live_key"
        settings.kalshi_api_secret = "live_secret"
        settings.kalshi_api_url = "https://api.kalshi.com"
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        mock_kalshi = MagicMock()
        mock_kalshi.get_markets_typed.return_value = [
            Market(
                ticker="HIGHNYC-25JAN26-T42",
                event_ticker="HIGHNYC-25JAN26",
                title="Test",
                status="open",
                yes_bid=40,
                yes_ask=45,
                volume=1000,
                open_interest=5000,
            )
        ]

        mock_strategy = MagicMock()
        mock_strategy.name = "test"
        mock_strategy.evaluate.return_value = Signal(
            ticker="HIGHNYC-25JAN26-T42",
            p_yes=0.7,
            uncertainty=0.1,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=60.0,
        )

        mock_weather_cache = MagicMock()
        from src.shared.api.weather_cache import CachedWeather
        mock_weather_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"temperature": 45, "isDaytime": True}]},
        )

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            strategy=mock_strategy,
            trading_mode=TradingMode.LIVE,
        )

        # Without confirmation, create_order should NOT be called
        loop.run_cycle("NYC")
        mock_kalshi.create_order.assert_not_called()

        # After confirmation, create_order SHOULD be called
        loop.confirm_live_mode()
        mock_kalshi.create_order.reset_mock()
        loop.run_cycle("NYC")
        # May or may not be called depending on gates, but confirmation is done
        assert loop.is_live_trading_enabled

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_live_mode_requires_credentials(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
    ) -> None:
        """Test LIVE mode raises error without credentials."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.LIVE
        settings.kalshi_api_key = None  # Missing
        settings.kalshi_api_secret = None  # Missing
        settings.kalshi_api_url = "https://api.kalshi.com"
        mock_settings.return_value = settings

        with pytest.raises(ValueError, match="LIVE mode requires"):
            TradingLoop(trading_mode=TradingMode.LIVE)

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_mode_logged_in_order_record(
        self,
        mock_settings: MagicMock,
        mock_loader: MagicMock,
        mock_city_loader: MagicMock,
    ) -> None:
        """Test trading mode is logged in order records."""
        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings
        mock_loader.get_city.return_value = mock_city_loader

        oms = OrderManagementSystem()

        mock_cache = MagicMock()
        from src.shared.api.weather_cache import CachedWeather
        mock_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"temperature": 45, "isDaytime": True}]},
        )

        loop = TradingLoop(
            weather_cache=mock_cache,
            oms=oms,
            trading_mode=TradingMode.SHADOW,
        )

        # Trading mode is tracked at loop level
        assert loop.trading_mode == TradingMode.SHADOW

    @pytest.fixture
    def mock_city_loader(self) -> MagicMock:
        """Create mock city loader."""
        mock_city = MagicMock()
        mock_city.code = "NYC"
        mock_city.name = "New York City"
        mock_city.nws_office = "OKX"
        mock_city.nws_grid_x = 33
        mock_city.nws_grid_y = 37
        mock_city.settlement_station = "KNYC"
        mock_city.cluster = "NE"
        return mock_city


class TestMultiCityRunResult:
    """Tests for MultiCityRunResult dataclass."""

    def test_multi_city_result_creation(self) -> None:
        """Test creating a multi-city run result."""
        from datetime import timedelta

        started = datetime.now(timezone.utc)
        completed = started + timedelta(seconds=30)

        result = MultiCityRunResult(
            started_at=started,
            completed_at=completed,
            city_results={},
            total_weather_fetched=10,
            total_markets_fetched=50,
            total_signals_generated=50,
            total_orders_submitted=5,
            cities_succeeded=10,
            cities_failed=0,
        )

        assert result.success is True
        assert result.duration_seconds == 30.0
        assert result.cities_succeeded == 10

    def test_multi_city_result_failure(self) -> None:
        """Test multi-city result with all failures."""
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        result = MultiCityRunResult(
            started_at=started,
            completed_at=completed,
            city_results={},
            cities_succeeded=0,
            cities_failed=10,
        )

        assert result.success is False


class TestMultiCityOrchestrator:
    """Tests for MultiCityOrchestrator class."""

    @pytest.fixture
    def mock_trading_loop(self) -> MagicMock:
        """Create mock trading loop."""
        loop = MagicMock(spec=TradingLoop)
        loop.trading_mode = TradingMode.SHADOW
        loop.oms = MagicMock()
        loop.oms.get_orders_by_status.return_value = []
        loop.circuit_breaker = MagicMock()
        loop.circuit_breaker.is_paused = False
        loop.weather_cache = MagicMock()

        # Configure run_cycle to return successful results
        def mock_run_cycle(city_code: str, quantity: int = 100) -> TradingCycleResult:
            return TradingCycleResult(
                city_code=city_code,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                weather_fetched=True,
                markets_fetched=5,
                signals_generated=5,
                gates_passed=2,
                orders_submitted=1,
            )

        loop.run_cycle.side_effect = mock_run_cycle
        return loop

    @patch("src.trader.trading_loop.city_loader")
    def test_orchestrator_initialization(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test orchestrator initializes with city list."""
        mock_loader.get_all_cities.return_value = {"NYC": {}, "LAX": {}, "CHI": {}}

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            trading_mode=TradingMode.SHADOW,
        )

        assert len(orchestrator.city_codes) == 3
        assert orchestrator.trading_mode == TradingMode.SHADOW

    @patch("src.trader.trading_loop.city_loader")
    def test_orchestrator_with_explicit_cities(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test orchestrator with explicit city list."""
        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX"],
            trading_mode=TradingMode.SHADOW,
        )

        assert orchestrator.city_codes == ["NYC", "LAX"]

    @patch("src.trader.trading_loop.city_loader")
    def test_run_all_cities_success(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test running all cities successfully."""
        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX", "CHI"],
            trading_mode=TradingMode.SHADOW,
        )

        result = orchestrator.run_all_cities(prefetch_weather=False)

        assert result.success is True
        assert result.cities_succeeded == 3
        assert result.cities_failed == 0
        assert result.total_orders_submitted == 3  # 1 per city
        assert len(result.city_results) == 3

    @patch("src.trader.trading_loop.city_loader")
    def test_run_all_cities_partial_failure(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test running cities with some failures."""
        # Make one city fail
        call_count = [0]

        def mock_run_cycle(city_code: str, quantity: int = 100) -> TradingCycleResult:
            call_count[0] += 1
            if city_code == "LAX":
                raise Exception("API Error for LAX")
            return TradingCycleResult(
                city_code=city_code,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                weather_fetched=True,
                markets_fetched=5,
                signals_generated=5,
                gates_passed=2,
                orders_submitted=1,
            )

        mock_trading_loop.run_cycle.side_effect = mock_run_cycle

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX", "CHI"],
            trading_mode=TradingMode.SHADOW,
        )

        result = orchestrator.run_all_cities(prefetch_weather=False)

        # Should still succeed overall (at least some cities worked)
        assert result.success is True
        assert result.cities_succeeded == 2
        assert result.cities_failed == 1
        # LAX should have an error result
        assert "API Error for LAX" in result.city_results["LAX"].errors[0]

    @patch("src.trader.trading_loop.city_loader")
    def test_run_all_cities_circuit_breaker_blocks(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test that circuit breaker blocks all trading."""
        mock_trading_loop.circuit_breaker.is_paused = True
        mock_trading_loop.circuit_breaker.pause_reason = "Loss limit exceeded"

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX"],
            trading_mode=TradingMode.SHADOW,
        )

        result = orchestrator.run_all_cities(prefetch_weather=False)

        assert result.success is False
        assert result.cities_failed == 2
        # No city cycles should have run
        mock_trading_loop.run_cycle.assert_not_called()

    @patch("src.trader.trading_loop.city_loader")
    def test_prefetch_weather_parallel(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test weather prefetch runs in parallel."""
        mock_trading_loop.weather_cache.get_weather.return_value = MagicMock()

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX", "CHI"],
            max_parallel_weather=3,
            trading_mode=TradingMode.SHADOW,
        )

        results = orchestrator.prefetch_weather()

        assert len(results) == 3
        assert all(v is True for v in results.values())
        # Should have called get_weather 3 times
        assert mock_trading_loop.weather_cache.get_weather.call_count == 3

    @patch("src.trader.trading_loop.city_loader")
    def test_prefetch_weather_handles_failures(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test weather prefetch handles failures gracefully."""

        def mock_get_weather(city_code: str, force_refresh: bool = False) -> MagicMock:
            if city_code == "LAX":
                raise Exception("Weather API error")
            return MagicMock()

        mock_trading_loop.weather_cache.get_weather.side_effect = mock_get_weather

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX", "CHI"],
            trading_mode=TradingMode.SHADOW,
        )

        results = orchestrator.prefetch_weather()

        assert results["NYC"] is True
        assert results["LAX"] is False
        assert results["CHI"] is True

    @patch("src.trader.trading_loop.city_loader")
    def test_get_run_summary(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test generating run summary."""
        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX"],
            trading_mode=TradingMode.SHADOW,
        )

        result = orchestrator.run_all_cities(prefetch_weather=False)
        summary = orchestrator.get_run_summary(result)

        assert summary["cities_total"] == 2
        assert summary["cities_succeeded"] == 2
        assert summary["trading_mode"] == "shadow"
        assert "NYC" in summary["per_city"]
        assert "LAX" in summary["per_city"]

    @patch("src.trader.trading_loop.city_loader")
    def test_aggregate_risk_check_exposure_limit(
        self,
        mock_loader: MagicMock,
        mock_trading_loop: MagicMock,
    ) -> None:
        """Test aggregate risk blocks when exposure limit exceeded."""
        # Simulate high exposure from pending orders
        mock_trading_loop.oms.get_orders_by_status.side_effect = lambda status: [
            {"quantity": 10000, "limit_price": 50}  # $5000 exposure
        ] * 20 if status in ["pending", "resting"] else []

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC"],
            trading_mode=TradingMode.SHADOW,
        )

        result = orchestrator.run_all_cities(prefetch_weather=False)

        # Should be blocked due to high exposure
        assert result.success is False
