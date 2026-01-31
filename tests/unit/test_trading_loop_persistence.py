"""Tests for trading loop persistence and additional coverage."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.api.response_models import Market
from src.shared.api.weather_cache import CachedWeather
from src.shared.config.settings import TradingMode
from src.trader.strategy import Signal


class TestTradingLoopPersistence:
    """Tests for trading loop persistence methods."""

    def _create_mock_trading_loop(self) -> MagicMock:
        """Create a mock trading loop with persistence configured."""
        from src.trader.trading_loop import TradingLoop

        mock_weather_cache = MagicMock()
        mock_kalshi = MagicMock()
        mock_oms = MagicMock()
        mock_risk = MagicMock()
        mock_circuit = MagicMock()
        mock_circuit.is_paused = False
        mock_strategy = MagicMock()
        mock_strategy.name = "daily_high_temp"

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            oms=mock_oms,
            risk_calculator=mock_risk,
            circuit_breaker=mock_circuit,
            strategy=mock_strategy,
            trading_mode=TradingMode.SHADOW,
        )

        return loop

    def test_persist_weather_no_repo(self) -> None:
        """Test _persist_weather returns None when no repo configured."""
        loop = self._create_mock_trading_loop()
        loop.weather_repo = None

        cached_weather = CachedWeather(
            city_code="NYC",
            forecast={"periods": []},
            observation={"temperature": {"value": 68.5}},
            fetched_at=datetime.now(timezone.utc),
            is_stale=False,
        )
        weather_data = {"city_code": "NYC", "temperature": 75}

        result = loop._persist_weather(cached_weather, weather_data)

        assert result is None

    def test_persist_weather_with_repo_success(self) -> None:
        """Test _persist_weather saves snapshot successfully."""
        loop = self._create_mock_trading_loop()
        mock_repo = MagicMock()
        mock_saved = MagicMock()
        mock_saved.id = 123
        mock_repo.save_snapshot.return_value = mock_saved
        loop.weather_repo = mock_repo

        cached_weather = CachedWeather(
            city_code="NYC",
            forecast={"periods": []},
            observation={"temperature": {"value": 68.5}},
            fetched_at=datetime.now(timezone.utc),
            is_stale=False,
        )
        weather_data = {"city_code": "NYC", "temperature": 75}

        # Lines 470-494: _persist_weather with observation temp
        result = loop._persist_weather(cached_weather, weather_data)

        assert result == 123
        mock_repo.save_snapshot.assert_called_once()

    def test_persist_weather_exception(self) -> None:
        """Test _persist_weather handles exception gracefully."""
        loop = self._create_mock_trading_loop()
        mock_repo = MagicMock()
        mock_repo.save_snapshot.side_effect = Exception("DB error")
        loop.weather_repo = mock_repo

        cached_weather = CachedWeather(
            city_code="NYC",
            forecast={"periods": []},
            observation=None,
            fetched_at=datetime.now(timezone.utc),
            is_stale=False,
        )
        weather_data = {"city_code": "NYC", "temperature": 75}

        # Lines 495-501: exception handling
        result = loop._persist_weather(cached_weather, weather_data)

        assert result is None

    def test_persist_market_no_repo(self) -> None:
        """Test _persist_market returns None when no repo configured."""
        loop = self._create_mock_trading_loop()
        loop.market_repo = None

        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
            yes_bid=45,
            yes_ask=48,
        )

        result = loop._persist_market(market, "NYC")

        assert result is None

    def test_persist_market_with_repo_success(self) -> None:
        """Test _persist_market saves snapshot successfully."""
        loop = self._create_mock_trading_loop()
        mock_repo = MagicMock()
        mock_saved = MagicMock()
        mock_saved.id = 456
        mock_repo.save_snapshot.return_value = mock_saved
        loop.market_repo = mock_repo

        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
            yes_bid=45,
            yes_ask=48,
            volume=1000,
            open_interest=500,
            strike_price=42.0,
        )

        # Lines 520-541: _persist_market
        result = loop._persist_market(market, "NYC")

        assert result == 456
        mock_repo.save_snapshot.assert_called_once()

    def test_persist_market_exception(self) -> None:
        """Test _persist_market handles exception gracefully."""
        loop = self._create_mock_trading_loop()
        mock_repo = MagicMock()
        mock_repo.save_snapshot.side_effect = Exception("DB error")
        loop.market_repo = mock_repo

        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
        )

        # Lines 542-548: exception handling
        result = loop._persist_market(market, "NYC")

        assert result is None

    def test_persist_signal_no_repo(self) -> None:
        """Test _persist_signal returns None when no repo configured."""
        loop = self._create_mock_trading_loop()
        loop.signal_repo = None

        signal = Signal(
            ticker="HIGHNYC-26JAN26-T42",
            decision="BUY",
            side="yes",
            p_yes=0.65,
            uncertainty=0.05,
            edge=5.0,
            max_price=70.0,
        )
        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
        )

        result = loop._persist_signal(signal, market, "NYC")

        assert result is None

    def test_persist_signal_with_repo_success(self) -> None:
        """Test _persist_signal saves signal successfully."""
        loop = self._create_mock_trading_loop()
        mock_repo = MagicMock()
        mock_saved = MagicMock()
        mock_saved.id = 789
        mock_repo.save_signal.return_value = mock_saved
        loop.signal_repo = mock_repo

        signal = Signal(
            ticker="HIGHNYC-26JAN26-T42",
            decision="BUY",
            side="yes",
            p_yes=0.65,
            uncertainty=0.05,
            edge=5.0,
            max_price=70.0,
        )
        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
        )

        # Lines 573-598: _persist_signal
        result = loop._persist_signal(
            signal, market, "NYC",
            weather_snapshot_id=123,
            market_snapshot_id=456,
        )

        assert result == 789
        mock_repo.save_signal.assert_called_once()

    def test_persist_signal_exception(self) -> None:
        """Test _persist_signal handles exception gracefully."""
        loop = self._create_mock_trading_loop()
        mock_repo = MagicMock()
        mock_repo.save_signal.side_effect = Exception("DB error")
        loop.signal_repo = mock_repo

        signal = Signal(
            ticker="HIGHNYC-26JAN26-T42",
            decision="BUY",
            side="yes",
            p_yes=0.65,
            uncertainty=0.05,
            edge=5.0,
            max_price=70.0,
        )
        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
        )

        # Lines 599-605: exception handling
        result = loop._persist_signal(signal, market, "NYC")

        assert result is None


class TestTradingLoopRiskChecks:
    """Tests for trading loop risk check branches."""

    def test_run_cycle_risk_limit_blocks_trade(self) -> None:
        """Test that risk limit check blocks trades."""
        from src.trader.trading_loop import TradingLoop

        mock_weather_cache = MagicMock()
        mock_kalshi = MagicMock()
        mock_oms = MagicMock()
        mock_risk = MagicMock()
        mock_circuit = MagicMock()
        mock_circuit.is_paused = False
        mock_strategy = MagicMock()
        mock_strategy.name = "daily_high_temp"

        # Risk calculator blocks trade
        mock_risk.check_trade_size.return_value = False

        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
            yes_bid=30,
            yes_ask=35,
            strike_price=42.0,
        )

        # Use DEMO mode so markets are fetched
        mock_kalshi.get_markets_typed.return_value = [market]

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            oms=mock_oms,
            risk_calculator=mock_risk,
            circuit_breaker=mock_circuit,
            strategy=mock_strategy,
            trading_mode=TradingMode.DEMO,
        )

        # Setup mocks for successful weather and market fetch
        mock_weather_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"isDaytime": True, "temperature": 75}]},
            observation={},
            fetched_at=datetime.now(timezone.utc),
            is_stale=False,
        )

        # Strategy returns BUY signal
        mock_strategy.evaluate.return_value = Signal(
            ticker=market.ticker,
            decision="BUY",
            side="yes",
            p_yes=0.85,
            uncertainty=0.03,
            edge=15.0,
            max_price=85.0,
        )

        with patch("src.trader.trading_loop.city_loader") as mock_loader:
            mock_city = MagicMock()
            mock_city.code = "NYC"
            mock_city.nws_station = "OKX"
            mock_city.lat = 40.7
            mock_city.lon = -74.0
            mock_loader.get_city.return_value = mock_city

            with patch("src.trader.trading_loop.check_all_gates") as mock_gates:
                mock_gates.return_value = (True, [])

                # Lines 371-373: trade_blocked_risk_limit
                result = loop.run_cycle("NYC", quantity=100)

                # Should have signals but no orders due to risk limit
                assert result.signals_generated >= 1
                assert result.orders_submitted == 0
                # Verify check_trade_size was called
                mock_risk.check_trade_size.assert_called()

    def test_run_cycle_city_exposure_blocks_trade(self) -> None:
        """Test that city exposure check blocks trades."""
        from src.trader.trading_loop import TradingLoop

        mock_weather_cache = MagicMock()
        mock_kalshi = MagicMock()
        mock_oms = MagicMock()
        mock_risk = MagicMock()
        mock_circuit = MagicMock()
        mock_circuit.is_paused = False
        mock_strategy = MagicMock()
        mock_strategy.name = "daily_high_temp"

        # Risk calculator allows trade size but blocks city exposure
        mock_risk.check_trade_size.return_value = True
        mock_risk.check_city_exposure.return_value = False

        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
            yes_bid=30,
            yes_ask=35,
            strike_price=42.0,
        )

        # Use DEMO mode so markets are fetched
        mock_kalshi.get_markets_typed.return_value = [market]

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            oms=mock_oms,
            risk_calculator=mock_risk,
            circuit_breaker=mock_circuit,
            strategy=mock_strategy,
            trading_mode=TradingMode.DEMO,
        )

        # Setup mocks
        mock_weather_cache.get_weather.return_value = CachedWeather(
            city_code="NYC",
            forecast={"periods": [{"isDaytime": True, "temperature": 75}]},
            observation={},
            fetched_at=datetime.now(timezone.utc),
            is_stale=False,
        )

        mock_strategy.evaluate.return_value = Signal(
            ticker=market.ticker,
            decision="BUY",
            side="yes",
            p_yes=0.85,
            uncertainty=0.03,
            edge=15.0,
            max_price=85.0,
        )

        with patch("src.trader.trading_loop.city_loader") as mock_loader:
            mock_city = MagicMock()
            mock_city.code = "NYC"
            mock_city.nws_station = "OKX"
            mock_city.lat = 40.7
            mock_city.lon = -74.0
            mock_loader.get_city.return_value = mock_city

            with patch("src.trader.trading_loop.check_all_gates") as mock_gates:
                mock_gates.return_value = (True, [])

                # Lines 375-379: trade_blocked_city_exposure
                result = loop.run_cycle("NYC", quantity=100)

                assert result.orders_submitted == 0
                # Verify check_city_exposure was called
                mock_risk.check_city_exposure.assert_called()


class TestTradingLoopSubmitOrder:
    """Tests for _submit_order in different modes."""

    def test_submit_order_returns_order_for_non_live_mode(self) -> None:
        """Test that _submit_order returns order dict."""
        from src.trader.trading_loop import TradingLoop

        mock_weather_cache = MagicMock()
        mock_kalshi = MagicMock()
        mock_oms = MagicMock()
        mock_risk = MagicMock()
        mock_circuit = MagicMock()
        mock_strategy = MagicMock()

        mock_oms.submit_order.return_value = {
            "intent_key": "test-key",
            "status": "pending",
        }

        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            oms=mock_oms,
            risk_calculator=mock_risk,
            circuit_breaker=mock_circuit,
            strategy=mock_strategy,
            trading_mode=TradingMode.SHADOW,
        )

        signal = Signal(
            ticker="TEST",
            decision="BUY",
            side="yes",
            p_yes=0.7,
            uncertainty=0.05,
            edge=10.0,
            max_price=70.0,
        )

        mock_city = MagicMock()
        mock_city.code = "NYC"

        market = Market(
            ticker="TEST",
            event_ticker="EVENT",
            title="Test",
            status="open",
        )

        # SHADOW mode: returns at line 658
        result = loop._submit_order(signal, mock_city, market, 100)

        assert result is not None
        assert result["intent_key"] == "test-key"

    def test_submit_order_demo_mode_no_kalshi_client(self) -> None:
        """Test _submit_order in DEMO mode without kalshi_client returns order (line 720)."""
        from src.trader.trading_loop import TradingLoop

        mock_weather_cache = MagicMock()
        mock_kalshi = MagicMock()  # Provide mock to satisfy init
        mock_oms = MagicMock()
        mock_risk = MagicMock()
        mock_circuit = MagicMock()
        mock_strategy = MagicMock()

        mock_oms.submit_order.return_value = {
            "intent_key": "demo-no-client-key",
            "status": "pending",
        }

        # Create with mock kalshi client first
        loop = TradingLoop(
            kalshi_client=mock_kalshi,
            weather_cache=mock_weather_cache,
            oms=mock_oms,
            risk_calculator=mock_risk,
            circuit_breaker=mock_circuit,
            strategy=mock_strategy,
            trading_mode=TradingMode.DEMO,
        )

        # Then set kalshi_client to None to simulate misconfigured state
        # This allows us to reach line 720 (return at end of _submit_order)
        loop.kalshi_client = None  # type: ignore[assignment]

        signal = Signal(
            ticker="TEST",
            decision="BUY",
            side="yes",
            p_yes=0.7,
            uncertainty=0.05,
            edge=10.0,
            max_price=70.0,
        )

        mock_city = MagicMock()
        mock_city.code = "NYC"

        market = Market(
            ticker="TEST",
            event_ticker="EVENT",
            title="Test",
            status="open",
        )

        # Line 720: return order at end of _submit_order
        # This is reached when kalshi_client is None/falsy in non-SHADOW mode
        result = loop._submit_order(signal, mock_city, market, 100)

        assert result is not None
        assert result["intent_key"] == "demo-no-client-key"


class TestMultiCityOrchestratorPrefetch:
    """Tests for MultiCityOrchestrator prefetch functionality."""

    def test_run_all_cities_with_prefetch_true(self) -> None:
        """Test run_all_cities calls prefetch when enabled."""
        from src.trader.trading_loop import MultiCityOrchestrator, TradingLoop

        mock_trading_loop = MagicMock(spec=TradingLoop)
        mock_trading_loop.trading_mode = TradingMode.SHADOW
        mock_trading_loop.circuit_breaker = MagicMock()
        mock_trading_loop.circuit_breaker.is_paused = False
        mock_trading_loop.oms = MagicMock()
        mock_trading_loop.oms.get_orders_by_status.return_value = []
        mock_trading_loop.weather_cache = MagicMock()

        # Make run_cycle return a valid result
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.weather_fetched = True
        mock_result.markets_fetched = 5
        mock_result.signals_generated = 3
        mock_result.orders_submitted = 2
        mock_result.errors = []
        mock_trading_loop.run_cycle.return_value = mock_result

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC"],
            trading_mode=TradingMode.SHADOW,
        )

        # Mock prefetch
        with patch.object(orchestrator, "prefetch_weather") as mock_prefetch:
            mock_prefetch.return_value = {"NYC": True}

            # Line 869: prefetch_weather called when prefetch_weather=True
            result = orchestrator.run_all_cities(prefetch_weather=True)

            mock_prefetch.assert_called_once()

    def test_run_all_cities_without_prefetch(self) -> None:
        """Test run_all_cities skips prefetch when disabled."""
        from src.trader.trading_loop import MultiCityOrchestrator, TradingLoop

        mock_trading_loop = MagicMock(spec=TradingLoop)
        mock_trading_loop.trading_mode = TradingMode.SHADOW
        mock_trading_loop.circuit_breaker = MagicMock()
        mock_trading_loop.circuit_breaker.is_paused = False
        mock_trading_loop.oms = MagicMock()
        mock_trading_loop.oms.get_orders_by_status.return_value = []

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.weather_fetched = True
        mock_result.markets_fetched = 5
        mock_result.signals_generated = 3
        mock_result.orders_submitted = 2
        mock_result.errors = []
        mock_trading_loop.run_cycle.return_value = mock_result

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC"],
            trading_mode=TradingMode.SHADOW,
        )

        with patch.object(orchestrator, "prefetch_weather") as mock_prefetch:
            # Test with prefetch_weather=False
            result = orchestrator.run_all_cities(prefetch_weather=False)

            mock_prefetch.assert_not_called()
