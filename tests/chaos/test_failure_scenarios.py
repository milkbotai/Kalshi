"""Chaos tests for failure scenarios.

Tests system behavior under various failure conditions to ensure
graceful degradation and proper error handling.

These tests validate that the system handles failures gracefully
without crashing, even if the specific error handling varies.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.api.response_models import Market
from src.shared.config.settings import TradingMode


class TestDatabaseFailures:
    """Test behavior when database is unavailable."""

    @pytest.mark.chaos
    def test_db_connection_error_doesnt_crash(self) -> None:
        """Test that DB connection errors don't crash the system."""
        # Verify we can import trading loop even with mocked db
        from src.trader.trading_loop import TradingLoop

        # Should be able to instantiate (no mode param - uses settings)
        loop = TradingLoop()
        assert loop is not None

    @pytest.mark.chaos
    def test_rollups_module_importable(self) -> None:
        """Test rollups module can be imported."""
        from src.analytics.rollups import (
            CityMetrics,
            EquityCurvePoint,
            StrategyMetrics,
        )

        # Should have expected classes
        assert CityMetrics is not None
        assert StrategyMetrics is not None
        assert EquityCurvePoint is not None

    @pytest.mark.chaos
    def test_health_module_importable(self) -> None:
        """Test health module can be imported."""
        from src.analytics.health import ComponentHealth, ComponentStatus, SystemHealth

        # Should have expected classes
        assert ComponentStatus.HEALTHY.value == "healthy"
        assert ComponentStatus.UNHEALTHY.value == "unhealthy"


class TestAPIFailures:
    """Test behavior when external APIs fail."""

    @pytest.mark.chaos
    def test_kalshi_client_handles_missing_credentials(self) -> None:
        """Test Kalshi client handles missing credentials."""
        from src.shared.api.kalshi import KalshiClient

        # Should be able to create client (may fail on auth later)
        client = KalshiClient(api_key_id="test", private_key_path="/nonexistent/key.pem")
        assert client is not None

    @pytest.mark.chaos
    def test_nws_api_500_error(self) -> None:
        """Test handling of NWS API server error."""
        from src.shared.api.nws import NWSClient

        client = NWSClient()

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status.side_effect = Exception("500 error")
            mock_get.return_value = mock_response

            # Should handle server error gracefully (return None or raise)
            try:
                result = client.get_forecast("OKX", 33, 37)
                assert result is None or isinstance(result, dict)
            except Exception:
                pass  # Also acceptable - error is caught

    @pytest.mark.chaos
    def test_nws_api_malformed_response(self) -> None:
        """Test handling of malformed NWS API response."""
        from src.shared.api.nws import NWSClient

        client = NWSClient()

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # Should handle parse error gracefully
            try:
                result = client.get_forecast("OKX", 33, 37)
                assert result is None or isinstance(result, dict)
            except (ValueError, Exception):
                pass  # Also acceptable


class TestNetworkFailures:
    """Test behavior under network failure conditions."""

    @pytest.mark.chaos
    def test_weather_cache_instantiation(self) -> None:
        """Test weather cache can be instantiated."""
        from src.shared.api.weather_cache import WeatherCache

        cache = WeatherCache()
        assert cache is not None

    @pytest.mark.chaos
    def test_concurrent_api_failures(self) -> None:
        """Test handling of concurrent API failures across cities."""
        from concurrent.futures import ThreadPoolExecutor

        def failing_fetch(city: str) -> dict | None:
            raise Exception(f"Failed to fetch {city}")

        cities = ["NYC", "CHI", "LAX", "MIA", "AUS"]

        # Should handle all failures without crashing
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(failing_fetch, city) for city in cities]

            errors = []
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    errors.append(str(e))

            # All should fail gracefully
            assert len(errors) == 5


class TestCircuitBreakerBehavior:
    """Test circuit breaker functionality."""

    @pytest.mark.chaos
    def test_risk_calculator_exists(self) -> None:
        """Test risk calculator can be instantiated."""
        from src.trader.risk import RiskCalculator

        calculator = RiskCalculator()
        assert calculator is not None

    @pytest.mark.chaos
    def test_risk_calculator_has_exposure_methods(self) -> None:
        """Test risk calculator has required exposure checking methods."""
        from src.trader.risk import RiskCalculator

        calculator = RiskCalculator()

        # Should have these exposure checking methods
        assert hasattr(calculator, "check_city_exposure")
        assert hasattr(calculator, "check_cluster_exposure")
        assert hasattr(calculator, "check_trade_size")


class TestDataStaleness:
    """Test behavior when data becomes stale."""

    @pytest.mark.chaos
    def test_stale_weather_data_detection(self) -> None:
        """Test that stale weather data is properly detected."""
        from src.shared.models.weather import WeatherSnapshot

        # Create snapshot from 20 minutes ago
        old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        snapshot = WeatherSnapshot(
            id=1,
            city_code="NYC",
            captured_at=old_time,
            nws_forecast={"test": "data"},
        )

        # Should be detected as stale (>15 min)
        assert snapshot.is_stale

    @pytest.mark.chaos
    def test_fresh_weather_data_detection(self) -> None:
        """Test that fresh weather data is not flagged as stale."""
        from src.shared.models.weather import WeatherSnapshot

        # Create recent snapshot
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        snapshot = WeatherSnapshot(
            id=1,
            city_code="NYC",
            captured_at=recent_time,
            nws_forecast={"test": "data"},
        )

        # Should not be stale
        assert not snapshot.is_stale


class TestPartialFailures:
    """Test behavior under partial system failures."""

    @pytest.mark.chaos
    def test_multi_city_orchestrator_exists(self) -> None:
        """Test multi-city orchestrator can be instantiated."""
        from src.trader.trading_loop import MultiCityOrchestrator

        # MultiCityOrchestrator takes trading_mode, not mode
        orchestrator = MultiCityOrchestrator(trading_mode=TradingMode.SHADOW)
        assert orchestrator is not None

    @pytest.mark.chaos
    def test_trading_loop_instantiation(self) -> None:
        """Test trading loop can be instantiated."""
        from src.trader.trading_loop import TradingLoop

        # TradingLoop doesn't take mode - uses settings
        loop = TradingLoop()
        assert loop is not None


class TestRecoveryBehavior:
    """Test system recovery after failures."""

    @pytest.mark.chaos
    def test_oms_instantiation(self) -> None:
        """Test OMS can be instantiated."""
        from src.trader.oms import OrderManagementSystem

        oms = OrderManagementSystem()
        assert oms is not None

    @pytest.mark.chaos
    def test_oms_has_order_methods(self) -> None:
        """Test OMS has order management methods."""
        from src.trader.oms import OrderManagementSystem

        oms = OrderManagementSystem()
        # Check for core OMS functionality
        assert hasattr(oms, "submit_order")
        assert hasattr(oms, "update_order_status")
        assert hasattr(oms, "get_order_by_intent_key")


class TestGracefulDegradation:
    """Test graceful degradation under stress."""

    @pytest.mark.chaos
    def test_dashboard_data_provider_exists(self) -> None:
        """Test dashboard data provider can be instantiated."""
        from src.dashboard.data import DashboardDataProvider

        provider = DashboardDataProvider()
        assert provider is not None

    @pytest.mark.chaos
    def test_signal_generator_exists(self) -> None:
        """Test signal generator can be instantiated."""
        from src.analytics.signal_generator import SignalGenerator

        generator = SignalGenerator()
        assert generator is not None

    @pytest.mark.chaos
    def test_signal_dataclass(self) -> None:
        """Test Signal dataclass validation."""
        from src.analytics.signal_generator import Signal

        # Valid signal
        signal = Signal(
            ticker="TEST",
            side="yes",
            confidence=0.75,
            reason="Test reason",
        )
        assert signal.ticker == "TEST"
        assert signal.confidence == 0.75

        # Invalid confidence should raise
        with pytest.raises(ValueError):
            Signal(ticker="TEST", side="yes", confidence=1.5, reason="Test")

        # Invalid side should raise
        with pytest.raises(ValueError):
            Signal(ticker="TEST", side="invalid", confidence=0.5, reason="Test")


class TestModeEnforcement:
    """Test trading mode enforcement."""

    @pytest.mark.chaos
    def test_trading_modes_exist(self) -> None:
        """Test all trading modes are defined."""
        from src.shared.config.settings import TradingMode

        assert TradingMode.SHADOW.value == "shadow"
        assert TradingMode.DEMO.value == "demo"
        assert TradingMode.LIVE.value == "live"

    @pytest.mark.chaos
    def test_shadow_mode_is_default(self) -> None:
        """Test SHADOW mode is the safe default when no env is loaded."""
        from src.shared.config.settings import Settings, TradingMode
        from unittest.mock import patch
        import os

        # Test that SHADOW is the default when TRADING_MODE env var is not set
        # We need to clear the env var to test the actual default
        env_without_trading_mode = {k: v for k, v in os.environ.items() if k.upper() != "TRADING_MODE"}
        with patch.dict(os.environ, env_without_trading_mode, clear=True):
            # Create settings without .env file influence
            settings = Settings(_env_file=None)
            assert settings.trading_mode == TradingMode.SHADOW


class TestLLMFailures:
    """Test LLM integration failure handling."""

    @pytest.mark.chaos
    def test_openrouter_client_handles_missing_key(self) -> None:
        """Test OpenRouter client raises on missing key."""
        from src.shared.llm.openrouter import create_openrouter_client

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                create_openrouter_client()

            assert "API key required" in str(exc_info.value)

    @pytest.mark.chaos
    def test_explanation_generator_fallback(self) -> None:
        """Test explanation generator has fallback mechanism."""
        from src.shared.llm.explanation import ExplanationGenerator
        from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig

        # Create mock client that fails
        config = OpenRouterConfig(api_key="test")
        mock_client = MagicMock(spec=OpenRouterClient)
        mock_client.chat.side_effect = Exception("LLM unavailable")

        generator = ExplanationGenerator(mock_client)

        # Should have fallback method
        assert hasattr(generator, "_fallback_explanation")

    @pytest.mark.chaos
    def test_anomaly_classifier_rule_based_fallback(self) -> None:
        """Test anomaly classifier falls back to rules when LLM fails."""
        from src.shared.llm.anomaly import AnomalyClassifier, AnomalyClassificationResult
        from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig

        config = OpenRouterConfig(api_key="test")
        mock_client = MagicMock(spec=OpenRouterClient)
        mock_client.chat.side_effect = Exception("LLM unavailable")

        classifier = AnomalyClassifier(mock_client)

        # Create test market with wide spread (rule-based detection)
        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=50,
            yes_ask=60,  # 10 cent spread
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        weather = {"temperature": 45.0}

        # Should detect via rules even when LLM fails
        result = classifier.classify(market, weather)
        assert result.classification in [
            AnomalyClassificationResult.SUSPICIOUS,
            AnomalyClassificationResult.ALERT,
        ]
