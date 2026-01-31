"""Tests to achieve 100% code coverage for uncovered lines.

Covers edge cases, error paths, and rarely-executed branches.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# kalshi.py coverage tests
# =============================================================================


class TestKalshiCoverageGaps:
    """Tests for uncovered lines in kalshi.py."""

    @patch("requests.Session.request")
    @patch("requests.Session.post")
    def test_get_market_typed_returns_market_on_empty_ticker(
        self, mock_post: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_market_typed returns Market even with empty ticker."""
        from src.shared.api.kalshi import KalshiClient

        # Mock auth
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        mock_response = MagicMock()
        mock_response.status_code = 200
        # Return market with empty ticker - Pydantic allows empty string
        mock_response.json.return_value = {"market": {"ticker": "", "event_ticker": "", "title": ""}}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        market = client.get_market_typed("TEST")

        # Empty ticker is valid, returns Market with empty ticker
        assert market is not None
        assert market.ticker == ""

    @patch("requests.Session.request")
    @patch("requests.Session.post")
    def test_get_orderbook_typed_handles_invalid_level_data(
        self, mock_post: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test get_orderbook_typed handles invalid level data."""
        from src.shared.api.kalshi import KalshiClient

        # Mock auth
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        mock_response = MagicMock()
        mock_response.status_code = 200
        # Include level that will raise exception during parsing
        mock_response.json.return_value = {
            "orderbook": {
                "yes": [
                    {"price": 45, "count": 100},
                    {"price": "invalid", "count": "bad"},  # Will cause parse error
                ],
                "no": [
                    {"price": None, "count": None},  # Another invalid level
                ],
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        orderbook = client.get_orderbook_typed("TEST")

        # Should have parsed valid level, skipped invalid ones
        assert len(orderbook.yes) >= 1

    @patch("requests.Session.request")
    @patch("requests.Session.post")
    def test_calculate_spread_returns_none_when_market_none(
        self, mock_post: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test calculate_spread returns None when market not found."""
        from src.shared.api.kalshi import KalshiClient

        # Mock auth
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"market": {}}
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        spread = client.calculate_spread("NONEXISTENT")

        assert spread is None

    @patch("requests.Session.request")
    @patch("requests.Session.post")
    def test_calculate_spread_with_valid_market(
        self, mock_post: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test calculate_spread with valid market data."""
        from src.shared.api.kalshi import KalshiClient

        # Mock auth
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "test_token"}
        mock_post.return_value = mock_auth_response

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "market": {
                "ticker": "TEST",
                "event_ticker": "TEST",
                "title": "Test Market",
                "status": "open",
                "yes_bid": 45,
                "yes_ask": 50,
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key="test", api_secret="test")
        spread = client.calculate_spread("TEST")

        assert spread == 5


# =============================================================================
# anomaly.py coverage tests
# =============================================================================


class TestAnomalyCoverageGaps:
    """Tests for uncovered lines in anomaly.py."""

    def test_rule_based_detection_with_datetime_captured_at(self) -> None:
        """Test _rule_based_detection when captured_at is already datetime."""
        from src.shared.api.response_models import Market
        from src.shared.llm.anomaly import AnomalyClassifier, AnomalyClassificationResult
        from src.shared.llm.openrouter import OpenRouterClient

        mock_client = MagicMock(spec=OpenRouterClient)
        classifier = AnomalyClassifier(mock_client)

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=55,
            yes_ask=58,
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        # Pass captured_at as datetime object (not string)
        recent_time = datetime.now(timezone.utc)
        weather = {
            "temperature": 45.0,
            "captured_at": recent_time,  # Already a datetime, not a string
        }

        result = classifier._rule_based_detection(market, weather, None)
        # Should handle datetime object without error
        assert result.classification == AnomalyClassificationResult.NORMAL

    def test_rule_based_detection_with_stale_datetime(self) -> None:
        """Test _rule_based_detection with stale datetime object."""
        from src.shared.api.response_models import Market
        from src.shared.llm.anomaly import AnomalyClassifier, AnomalyClassificationResult, AnomalyType
        from src.shared.llm.openrouter import OpenRouterClient, LLMResponse

        mock_client = MagicMock(spec=OpenRouterClient)
        # Mock LLM response for SUSPICIOUS case
        mock_client.chat.return_value = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "data_stale", "reason": "Data is old", "confidence": 0.8}',
            model="test-model",
            latency_ms=100.0,
        )
        classifier = AnomalyClassifier(mock_client)

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=55,
            yes_ask=58,
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        # Pass stale captured_at as datetime object
        old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        weather = {
            "temperature": 45.0,
            "captured_at": old_time,  # Stale datetime
        }

        result = classifier.classify(market, weather)
        # Should detect stale data
        assert result.anomaly_type == AnomalyType.DATA_STALE

    def test_rule_based_detection_with_invalid_string_captured_at(self) -> None:
        """Test _rule_based_detection with invalid captured_at string."""
        from src.shared.api.response_models import Market
        from src.shared.llm.anomaly import AnomalyClassifier, AnomalyClassificationResult
        from src.shared.llm.openrouter import OpenRouterClient

        mock_client = MagicMock(spec=OpenRouterClient)
        classifier = AnomalyClassifier(mock_client)

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=55,
            yes_ask=58,
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        # Invalid string that can't be parsed as datetime
        weather = {
            "temperature": 45.0,
            "captured_at": "not-a-valid-datetime",
        }

        result = classifier._rule_based_detection(market, weather, None)
        # Should handle gracefully and return NORMAL
        assert result.classification == AnomalyClassificationResult.NORMAL

    def test_parse_response_with_invalid_anomaly_type(self) -> None:
        """Test _parse_response with invalid anomaly_type falls back."""
        from src.shared.api.response_models import Market
        from src.shared.llm.anomaly import (
            AnomalyClassifier,
            AnomalyClassification,
            AnomalyClassificationResult,
            AnomalyType,
        )
        from src.shared.llm.openrouter import LLMResponse, OpenRouterClient

        mock_client = MagicMock(spec=OpenRouterClient)
        classifier = AnomalyClassifier(mock_client)

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=42,
        )

        rule_based = AnomalyClassification(
            ticker="TEST",
            classification=AnomalyClassificationResult.SUSPICIOUS,
            anomaly_type=AnomalyType.WIDE_SPREAD,
            reason="Test",
            confidence=0.8,
        )

        # Response with invalid anomaly_type
        response = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "invalid_type", "reason": "test", "confidence": 0.8}',
            model="test-model",
            latency_ms=100.0,
        )

        result = classifier._parse_response(response, market, rule_based)

        # Should fall back to rule_based anomaly_type
        assert result.anomaly_type == AnomalyType.WIDE_SPREAD

    def test_parse_response_clamps_confidence_high(self) -> None:
        """Test _parse_response clamps confidence > 1.0."""
        from src.shared.api.response_models import Market
        from src.shared.llm.anomaly import (
            AnomalyClassifier,
            AnomalyClassification,
            AnomalyClassificationResult,
            AnomalyType,
        )
        from src.shared.llm.openrouter import LLMResponse, OpenRouterClient

        mock_client = MagicMock(spec=OpenRouterClient)
        classifier = AnomalyClassifier(mock_client)

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=42,
        )

        rule_based = AnomalyClassification(
            ticker="TEST",
            classification=AnomalyClassificationResult.SUSPICIOUS,
            anomaly_type=AnomalyType.WIDE_SPREAD,
            reason="Test",
            confidence=0.8,
        )

        # Response with confidence > 1.0
        response = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "wide_spread", "reason": "test", "confidence": 1.5}',
            model="test-model",
            latency_ms=100.0,
        )

        result = classifier._parse_response(response, market, rule_based)

        # Confidence should be clamped to 1.0
        assert result.confidence == 1.0

    def test_parse_response_clamps_confidence_low(self) -> None:
        """Test _parse_response clamps confidence < 0.0."""
        from src.shared.api.response_models import Market
        from src.shared.llm.anomaly import (
            AnomalyClassifier,
            AnomalyClassification,
            AnomalyClassificationResult,
            AnomalyType,
        )
        from src.shared.llm.openrouter import LLMResponse, OpenRouterClient

        mock_client = MagicMock(spec=OpenRouterClient)
        classifier = AnomalyClassifier(mock_client)

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=42,
        )

        rule_based = AnomalyClassification(
            ticker="TEST",
            classification=AnomalyClassificationResult.SUSPICIOUS,
            anomaly_type=AnomalyType.WIDE_SPREAD,
            reason="Test",
            confidence=0.8,
        )

        # Response with confidence < 0.0
        response = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "wide_spread", "reason": "test", "confidence": -0.5}',
            model="test-model",
            latency_ms=100.0,
        )

        result = classifier._parse_response(response, market, rule_based)

        # Confidence should be clamped to 0.0
        assert result.confidence == 0.0

    def test_parse_response_json_key_error(self) -> None:
        """Test _parse_response handles KeyError in JSON."""
        from src.shared.api.response_models import Market
        from src.shared.llm.anomaly import (
            AnomalyClassifier,
            AnomalyClassification,
            AnomalyClassificationResult,
            AnomalyType,
        )
        from src.shared.llm.openrouter import LLMResponse, OpenRouterClient

        mock_client = MagicMock(spec=OpenRouterClient)
        classifier = AnomalyClassifier(mock_client)

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=42,
        )

        rule_based = AnomalyClassification(
            ticker="TEST",
            classification=AnomalyClassificationResult.SUSPICIOUS,
            anomaly_type=AnomalyType.WIDE_SPREAD,
            reason="Test",
            confidence=0.8,
        )

        # Invalid JSON that will cause parse error
        response = LLMResponse(
            content="not valid json at all",
            model="test-model",
            latency_ms=100.0,
        )

        result = classifier._parse_response(response, market, rule_based)

        # Should return rule_based with LLM metadata
        assert result.model_used == "test-model"
        assert result.latency_ms == 100.0

    def test_parse_response_with_code_block_no_json_marker(self) -> None:
        """Test _parse_response handles code block without json marker."""
        from src.shared.api.response_models import Market
        from src.shared.llm.anomaly import (
            AnomalyClassifier,
            AnomalyClassification,
            AnomalyClassificationResult,
            AnomalyType,
        )
        from src.shared.llm.openrouter import LLMResponse, OpenRouterClient

        mock_client = MagicMock(spec=OpenRouterClient)
        classifier = AnomalyClassifier(mock_client)

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=42,
        )

        rule_based = AnomalyClassification(
            ticker="TEST",
            classification=AnomalyClassificationResult.SUSPICIOUS,
            anomaly_type=AnomalyType.WIDE_SPREAD,
            reason="Test",
            confidence=0.8,
        )

        # Code block without json marker
        response = LLMResponse(
            content='```\n{"classification": "ALERT", "anomaly_type": "wide_spread", "reason": "test", "confidence": 0.9}\n```',
            model="test-model",
            latency_ms=100.0,
        )

        result = classifier._parse_response(response, market, rule_based)

        assert result.classification == AnomalyClassificationResult.ALERT


# =============================================================================
# openrouter.py coverage tests
# =============================================================================


class TestOpenRouterCoverageGaps:
    """Tests for uncovered lines in openrouter.py."""

    @patch("httpx.Client.post")
    def test_parse_response_empty_choices(self, mock_post: MagicMock) -> None:
        """Test _parse_response raises error on empty choices."""
        from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig, OpenRouterError

        config = OpenRouterConfig(api_key="test-key")
        client = OpenRouterClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}
        mock_post.return_value = mock_response

        with pytest.raises(OpenRouterError) as exc_info:
            client.chat("Hello")

        assert "No choices" in str(exc_info.value)

    @patch("httpx.Client.post")
    def test_extract_error_exception_handling(self, mock_post: MagicMock) -> None:
        """Test _extract_error handles JSON parse failure."""
        from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig, OpenRouterError

        config = OpenRouterConfig(api_key="test-key")
        client = OpenRouterClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 500
        # json() raises exception
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Server Error Text"
        mock_post.return_value = mock_response

        with pytest.raises(OpenRouterError) as exc_info:
            client.chat("Hello")

        # Should use response.text as fallback
        assert "500" in str(exc_info.value)

    def test_create_openrouter_client_no_key_raises(self) -> None:
        """Test create_openrouter_client raises without API key."""
        from src.shared.llm.openrouter import create_openrouter_client
        import os

        # Save and clear the environment variable
        original_key = os.environ.pop("OPENROUTER_API_KEY", None)

        try:
            with pytest.raises(ValueError) as exc_info:
                create_openrouter_client()

            assert "API key required" in str(exc_info.value)
        finally:
            # Restore the environment variable if it existed
            if original_key is not None:
                os.environ["OPENROUTER_API_KEY"] = original_key

    def test_extract_error_with_dict_error(self) -> None:
        """Test _extract_error when error is a dict."""
        from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig
        import httpx

        config = OpenRouterConfig(api_key="test-key")
        client = OpenRouterClient(config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"error": {"message": "Detailed error message"}}

        error_msg = client._extract_error(mock_response)

        assert error_msg == "Detailed error message"

    def test_extract_error_with_string_error(self) -> None:
        """Test _extract_error when error is a string."""
        from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig
        import httpx

        config = OpenRouterConfig(api_key="test-key")
        client = OpenRouterClient(config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"error": "Simple error string"}

        error_msg = client._extract_error(mock_response)

        assert error_msg == "Simple error string"

    def test_extract_error_with_empty_text(self) -> None:
        """Test _extract_error when response.text is empty."""
        from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig
        import httpx

        config = OpenRouterConfig(api_key="test-key")
        client = OpenRouterClient(config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = Exception("Parse error")
        mock_response.text = ""

        error_msg = client._extract_error(mock_response)

        assert error_msg == "Unknown error"


# =============================================================================
# trading_loop.py coverage tests
# =============================================================================


class TestTradingLoopCoverageGaps:
    """Tests for uncovered lines in trading_loop.py."""

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_build_weather_data_with_is_daytime_key(
        self, mock_settings: MagicMock, mock_loader: MagicMock
    ) -> None:
        """Test _build_weather_data handles 'is_daytime' key variant."""
        from src.trader.trading_loop import TradingLoop
        from src.shared.config.settings import TradingMode

        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        mock_city = MagicMock()
        mock_city.code = "NYC"

        loop = TradingLoop(trading_mode=TradingMode.SHADOW)

        # Use 'is_daytime' instead of 'isDaytime'
        forecast = {
            "periods": [
                {"name": "Today", "temperature": 55, "is_daytime": True},
            ]
        }

        weather_data = loop._build_weather_data(forecast, mock_city)

        assert weather_data["temperature"] == 55
        assert weather_data["city_code"] == "NYC"

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_submit_order_generates_market_id_hash(
        self, mock_settings: MagicMock, mock_loader: MagicMock
    ) -> None:
        """Test _submit_order generates market_id from ticker hash."""
        from src.trader.trading_loop import TradingLoop
        from src.trader.strategy import Signal
        from src.shared.api.response_models import Market
        from src.shared.config.settings import TradingMode

        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        mock_city = MagicMock()
        mock_city.code = "NYC"

        loop = TradingLoop(trading_mode=TradingMode.SHADOW)

        signal = Signal(
            ticker="HIGHNYC-25JAN26-T42",
            p_yes=0.65,
            uncertainty=0.1,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=60.0,
        )

        market = Market(
            ticker="HIGHNYC-25JAN26-T42",
            event_ticker="HIGHNYC-25JAN26",
            title="Test",
            status="open",
            strike_price=42.0,
        )

        order = loop._submit_order(signal, mock_city, market, 100)

        # Order should be created with hashed market_id
        assert order is not None
        assert "intent_key" in order

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_prefetch_weather_handles_exception_in_thread(
        self, mock_settings: MagicMock, mock_loader: MagicMock
    ) -> None:
        """Test prefetch_weather handles exception in thread."""
        from src.trader.trading_loop import MultiCityOrchestrator, TradingLoop
        from src.shared.config.settings import TradingMode

        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        mock_trading_loop = MagicMock(spec=TradingLoop)
        mock_trading_loop.trading_mode = TradingMode.SHADOW
        mock_trading_loop.weather_cache = MagicMock()

        # Make weather fetch raise exception
        mock_trading_loop.weather_cache.get_weather.side_effect = Exception("Network error")

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC", "LAX"],
            trading_mode=TradingMode.SHADOW,
        )

        results = orchestrator.prefetch_weather()

        # All should fail
        assert results["NYC"] is False
        assert results["LAX"] is False

    @patch("src.trader.trading_loop.city_loader")
    @patch("src.trader.trading_loop.get_settings")
    def test_get_run_summary_includes_errors(
        self, mock_settings: MagicMock, mock_loader: MagicMock
    ) -> None:
        """Test get_run_summary includes per_city errors."""
        from src.trader.trading_loop import (
            MultiCityOrchestrator,
            MultiCityRunResult,
            TradingCycleResult,
            TradingLoop,
        )
        from src.shared.config.settings import TradingMode

        settings = MagicMock()
        settings.trading_mode = TradingMode.SHADOW
        mock_settings.return_value = settings

        mock_trading_loop = MagicMock(spec=TradingLoop)
        mock_trading_loop.trading_mode = TradingMode.SHADOW

        orchestrator = MultiCityOrchestrator(
            trading_loop=mock_trading_loop,
            city_codes=["NYC"],
            trading_mode=TradingMode.SHADOW,
        )

        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        # Create result with errors
        result = MultiCityRunResult(
            started_at=started,
            completed_at=completed,
            city_results={
                "NYC": TradingCycleResult(
                    city_code="NYC",
                    started_at=started,
                    completed_at=completed,
                    weather_fetched=False,
                    markets_fetched=0,
                    signals_generated=0,
                    gates_passed=0,
                    orders_submitted=0,
                    errors=["Weather fetch failed", "Another error"],
                ),
            },
            cities_succeeded=0,
            cities_failed=1,
        )

        summary = orchestrator.get_run_summary(result)

        # Should include errors in per_city
        assert "NYC" in summary["per_city"]
        assert len(summary["per_city"]["NYC"]["errors"]) == 2


# =============================================================================
# health.py coverage tests
# =============================================================================


class TestHealthCoverageGaps:
    """Tests for uncovered lines in health.py."""

    def test_check_degraded_components(self) -> None:
        """Test check_degraded_components function."""
        from src.analytics.health import (
            check_degraded_components,
            ComponentStatus,
            ComponentHealth,
            SystemHealth,
        )

        mock_engine = MagicMock()

        # Mock get_current_health to return components with various statuses
        with patch("src.analytics.health.get_current_health") as mock_get_health:
            mock_get_health.return_value = SystemHealth(
                checked_at=datetime.now(timezone.utc),
                overall_status=ComponentStatus.DEGRADED,
                components=[
                    ComponentHealth(
                        name="healthy_component",
                        status=ComponentStatus.HEALTHY,
                        last_check=datetime.now(timezone.utc),
                    ),
                    ComponentHealth(
                        name="degraded_component",
                        status=ComponentStatus.DEGRADED,
                        last_check=datetime.now(timezone.utc),
                    ),
                    ComponentHealth(
                        name="unhealthy_component",
                        status=ComponentStatus.UNHEALTHY,
                        last_check=datetime.now(timezone.utc),
                    ),
                ],
                total_healthy=1,
                total_degraded=1,
                total_unhealthy=1,
            )

            degraded = check_degraded_components(mock_engine)

            # Should return only degraded and unhealthy
            assert len(degraded) == 2
            assert all(
                c.status in (ComponentStatus.DEGRADED, ComponentStatus.UNHEALTHY)
                for c in degraded
            )

    def test_component_health_properties(self) -> None:
        """Test ComponentHealth is_healthy and is_degraded properties."""
        from src.analytics.health import ComponentHealth, ComponentStatus

        healthy = ComponentHealth(
            name="test",
            status=ComponentStatus.HEALTHY,
            last_check=datetime.now(timezone.utc),
        )
        assert healthy.is_healthy is True
        assert healthy.is_degraded is False

        degraded = ComponentHealth(
            name="test",
            status=ComponentStatus.DEGRADED,
            last_check=datetime.now(timezone.utc),
        )
        assert degraded.is_healthy is False
        assert degraded.is_degraded is True

    def test_system_health_is_system_healthy(self) -> None:
        """Test SystemHealth.is_system_healthy property."""
        from src.analytics.health import SystemHealth, ComponentStatus

        healthy_system = SystemHealth(
            checked_at=datetime.now(timezone.utc),
            overall_status=ComponentStatus.HEALTHY,
            components=[],
            total_healthy=1,
        )
        assert healthy_system.is_system_healthy is True

        unhealthy_system = SystemHealth(
            checked_at=datetime.now(timezone.utc),
            overall_status=ComponentStatus.UNHEALTHY,
            components=[],
            total_unhealthy=1,
        )
        assert unhealthy_system.is_system_healthy is False


# =============================================================================
# rollups.py coverage tests
# =============================================================================


class TestRollupsCoverageGaps:
    """Tests for uncovered lines in rollups.py."""

    def test_city_metrics_profit_factor_zero_wins(self) -> None:
        """Test CityMetrics.profit_factor when win_count is 0."""
        from datetime import date
        from src.analytics.rollups import CityMetrics

        metrics = CityMetrics(
            city_code="NYC",
            date=date.today(),
            trade_count=10,
            volume=Decimal("1000"),
            gross_pnl=Decimal("-100"),
            net_pnl=Decimal("-110"),
            fees=Decimal("10"),
            win_count=0,  # Zero wins
            loss_count=5,
            avg_position_size=Decimal("100"),
            max_position_size=Decimal("200"),
        )

        # profit_factor should return 0.0 when win_count is 0
        assert metrics.profit_factor == 0.0

    def test_city_metrics_profit_factor_zero_losses(self) -> None:
        """Test CityMetrics.profit_factor when loss_count is 0."""
        from datetime import date
        from src.analytics.rollups import CityMetrics

        metrics = CityMetrics(
            city_code="NYC",
            date=date.today(),
            trade_count=10,
            volume=Decimal("1000"),
            gross_pnl=Decimal("100"),
            net_pnl=Decimal("90"),
            fees=Decimal("10"),
            win_count=5,
            loss_count=0,  # Zero losses
            avg_position_size=Decimal("100"),
            max_position_size=Decimal("200"),
        )

        # profit_factor should return None when loss_count is 0
        assert metrics.profit_factor is None

    def test_city_metrics_win_rate(self) -> None:
        """Test CityMetrics.win_rate calculation."""
        from datetime import date
        from src.analytics.rollups import CityMetrics

        metrics = CityMetrics(
            city_code="NYC",
            date=date.today(),
            trade_count=10,
            volume=Decimal("1000"),
            gross_pnl=Decimal("100"),
            net_pnl=Decimal("90"),
            fees=Decimal("10"),
            win_count=3,
            loss_count=7,
            avg_position_size=Decimal("100"),
            max_position_size=Decimal("200"),
        )

        assert metrics.win_rate == 30.0

    def test_city_metrics_win_rate_zero_trades(self) -> None:
        """Test CityMetrics.win_rate when no trades."""
        from datetime import date
        from src.analytics.rollups import CityMetrics

        metrics = CityMetrics(
            city_code="NYC",
            date=date.today(),
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

    def test_strategy_metrics_conversion_rate(self) -> None:
        """Test StrategyMetrics.conversion_rate calculation."""
        from datetime import date
        from src.analytics.rollups import StrategyMetrics

        metrics = StrategyMetrics(
            strategy_name="test_strategy",
            date=date.today(),
            signal_count=100,
            trade_count=25,
            gross_pnl=Decimal("500"),
            net_pnl=Decimal("450"),
            fees=Decimal("50"),
            win_count=15,
            loss_count=10,
            avg_edge=Decimal("0.05"),
            avg_confidence=Decimal("0.75"),
        )

        assert metrics.conversion_rate == 25.0

    def test_strategy_metrics_conversion_rate_zero_signals(self) -> None:
        """Test StrategyMetrics.conversion_rate when no signals."""
        from datetime import date
        from src.analytics.rollups import StrategyMetrics

        metrics = StrategyMetrics(
            strategy_name="test_strategy",
            date=date.today(),
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


# =============================================================================
# signal_generator.py coverage tests
# =============================================================================


class TestSignalGeneratorCoverageGaps:
    """Tests for uncovered lines in signal_generator.py."""

    def test_combine_signals_no_consensus_logging(self) -> None:
        """Test combine_signals logs when no consensus."""
        from src.analytics.signal_generator import SignalGenerator, Signal

        generator = SignalGenerator()

        # Create signals with equal votes for yes and no
        signals = [
            Signal(ticker="TEST", side="yes", confidence=0.8, reason="Reason 1"),
            Signal(ticker="TEST", side="no", confidence=0.8, reason="Reason 2"),
        ]

        result = generator.combine_signals(signals)

        # Should return None when no consensus
        assert result is None

    def test_combine_signals_empty_list(self) -> None:
        """Test combine_signals with empty list."""
        from src.analytics.signal_generator import SignalGenerator

        generator = SignalGenerator()

        result = generator.combine_signals([])

        assert result is None


# =============================================================================
# nws.py coverage tests
# =============================================================================


class TestNWSCoverageGaps:
    """Tests for uncovered lines in nws.py."""

    @patch("requests.Session.get")
    def test_get_point_metadata(self, mock_get: MagicMock) -> None:
        """Test get_point_metadata function."""
        from src.shared.api.nws import NWSClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {
                "gridId": "OKX",
                "gridX": 33,
                "gridY": 37,
            }
        }
        mock_get.return_value = mock_response

        client = NWSClient()
        metadata = client.get_point_metadata(40.7128, -74.0060)

        assert "properties" in metadata
        assert metadata["properties"]["gridId"] == "OKX"
        mock_get.assert_called_once()


# =============================================================================
# response_models.py coverage tests
# =============================================================================


class TestResponseModelsCoverageGaps:
    """Tests for uncovered lines in response_models.py."""

    def test_orderbook_best_yes_ask(self) -> None:
        """Test Orderbook.best_yes_ask property."""
        from src.shared.api.response_models import Orderbook, OrderbookLevel

        orderbook = Orderbook(
            yes=[
                OrderbookLevel(price=45, quantity=100),
                OrderbookLevel(price=48, quantity=200),
                OrderbookLevel(price=42, quantity=50),
            ],
            no=[],
        )

        # best_yes_ask should return minimum price
        assert orderbook.best_yes_ask == 42

    def test_orderbook_empty_best_yes_ask(self) -> None:
        """Test Orderbook.best_yes_ask when empty."""
        from src.shared.api.response_models import Orderbook

        orderbook = Orderbook(yes=[], no=[])

        assert orderbook.best_yes_ask is None

    def test_orderbook_empty_best_yes_bid(self) -> None:
        """Test Orderbook.best_yes_bid when empty."""
        from src.shared.api.response_models import Orderbook

        orderbook = Orderbook(yes=[], no=[])

        assert orderbook.best_yes_bid is None


# =============================================================================
# weather_cache.py coverage tests
# =============================================================================


class TestWeatherCacheCoverageGaps:
    """Tests for uncovered lines in weather_cache.py."""

    def test_get_weather_convenience_function(self) -> None:
        """Test get_weather convenience function."""
        from src.shared.api.weather_cache import get_weather

        with patch("src.shared.api.weather_cache.get_weather_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.get_weather.return_value = MagicMock(city_code="NYC")
            mock_get_cache.return_value = mock_cache

            result = get_weather("NYC", force_refresh=True)

            mock_cache.get_weather.assert_called_once_with("NYC", True)
            assert result.city_code == "NYC"


# =============================================================================
# logging.py coverage tests
# =============================================================================


class TestLoggingCoverageGaps:
    """Tests for uncovered lines in logging.py."""

    def test_configure_logging_json_format(self) -> None:
        """Test configure_logging with JSON format."""
        from src.shared.config.logging import configure_logging

        with patch("src.shared.config.logging.settings") as mock_settings:
            mock_settings.log_format = "json"
            mock_settings.log_level = "INFO"

            # Should not raise
            configure_logging()


# =============================================================================
# Model imports coverage tests (TYPE_CHECKING blocks)
# =============================================================================


class TestModelImportsCoverage:
    """Tests to ensure model files are imported and TYPE_CHECKING blocks are covered."""

    def test_order_model_import(self) -> None:
        """Test order.py imports."""
        from src.shared.models.order import Order

        # Just importing covers the TYPE_CHECKING block
        assert Order is not None

    def test_position_model_import_and_close_position(self) -> None:
        """Test position.py imports and close_position method."""
        from src.shared.models.position import Position

        # Create a position instance to test close_position
        position = Position(
            market_id=1,
            ticker="TEST",
            side="yes",
            quantity=100,
            entry_price=50.0,
            total_cost=5000.0,
            status="open",
        )

        # Test close_position method
        close_time = datetime.now(timezone.utc)
        position.close_position(settlement_price=60.0, closed_at=close_time)

        assert position.status == "closed"
        assert position.settlement_price == 60.0
        assert position.closed_at == close_time
        assert position.realized_pnl == 1000.0  # (60 - 50) * 100

    def test_position_close_position_no_side(self) -> None:
        """Test position close_position for 'no' side."""
        from src.shared.models.position import Position

        position = Position(
            market_id=1,
            ticker="TEST",
            side="no",
            quantity=100,
            entry_price=50.0,
            total_cost=5000.0,
            status="open",
        )

        close_time = datetime.now(timezone.utc)
        position.close_position(settlement_price=40.0, closed_at=close_time)

        assert position.status == "closed"
        # For 'no' side: (entry - settlement) * quantity = (50 - 40) * 100 = 1000
        assert position.realized_pnl == 1000.0

    def test_position_update_pnl_yes_side(self) -> None:
        """Test position update_pnl for 'yes' side."""
        from src.shared.models.position import Position

        position = Position(
            market_id=1,
            ticker="TEST",
            side="yes",
            quantity=100,
            entry_price=50.0,
            total_cost=5000.0,
            status="open",
        )

        position.update_pnl(current_price=60.0)

        assert position.current_price == 60.0
        assert position.unrealized_pnl == 1000.0  # (60 - 50) * 100

    def test_position_update_pnl_no_side(self) -> None:
        """Test position update_pnl for 'no' side."""
        from src.shared.models.position import Position

        position = Position(
            market_id=1,
            ticker="TEST",
            side="no",
            quantity=100,
            entry_price=50.0,
            total_cost=5000.0,
            status="open",
        )

        position.update_pnl(current_price=40.0)

        assert position.current_price == 40.0
        assert position.unrealized_pnl == 1000.0  # (50 - 40) * 100

    def test_trade_model_import(self) -> None:
        """Test trade.py imports."""
        from src.shared.models.trade import Trade

        # Just importing covers the TYPE_CHECKING block
        assert Trade is not None

    def test_trade_calculate_pnl_buy(self) -> None:
        """Test Trade.calculate_pnl for buy action."""
        from src.shared.models.trade import Trade

        trade = Trade(
            market_id=1,
            ticker="TEST",
            side="yes",
            action="buy",
            quantity=100,
            price=50.0,
            total_cost=5000.0,
            fees=10.0,
            executed_at=datetime.now(timezone.utc),
        )

        pnl = trade.calculate_pnl(exit_price=60.0)

        # (60 - 50) * 100 - 10 = 990
        assert pnl == 990.0

    def test_trade_calculate_pnl_sell(self) -> None:
        """Test Trade.calculate_pnl for sell action."""
        from src.shared.models.trade import Trade

        trade = Trade(
            market_id=1,
            ticker="TEST",
            side="yes",
            action="sell",
            quantity=100,
            price=60.0,
            total_cost=6000.0,
            fees=10.0,
            executed_at=datetime.now(timezone.utc),
        )

        pnl = trade.calculate_pnl(exit_price=50.0)

        # (60 - 50) * 100 - 10 = 990
        assert pnl == 990.0

    def test_trade_notional_value(self) -> None:
        """Test Trade.notional_value property."""
        from src.shared.models.trade import Trade

        trade = Trade(
            market_id=1,
            ticker="TEST",
            side="yes",
            action="buy",
            quantity=100,
            price=50.0,
            total_cost=5000.0,
            fees=10.0,
            executed_at=datetime.now(timezone.utc),
        )

        assert trade.notional_value == 5000.0

    def test_order_model_properties(self) -> None:
        """Test Order model properties."""
        from src.shared.models.order import Order

        order = Order(
            market_id=1,
            ticker="TEST",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            limit_price=50.0,
            filled_quantity=50,
            remaining_quantity=50,
            status="partially_filled",
            submitted_at=datetime.now(timezone.utc),
        )

        assert order.is_filled is False
        assert order.fill_rate == 0.5

    def test_order_model_fully_filled(self) -> None:
        """Test Order model when fully filled."""
        from src.shared.models.order import Order

        order = Order(
            market_id=1,
            ticker="TEST",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            limit_price=50.0,
            filled_quantity=100,
            remaining_quantity=0,
            status="filled",
            submitted_at=datetime.now(timezone.utc),
        )

        assert order.is_filled is True
        assert order.fill_rate == 1.0

    def test_order_model_zero_quantity(self) -> None:
        """Test Order model with zero quantity."""
        from src.shared.models.order import Order

        order = Order(
            market_id=1,
            ticker="TEST",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=0,
            limit_price=50.0,
            filled_quantity=0,
            remaining_quantity=0,
            status="pending",
            submitted_at=datetime.now(timezone.utc),
        )

        assert order.fill_rate == 0.0

    def test_order_update_fill(self) -> None:
        """Test Order.update_fill method."""
        from src.shared.models.order import Order

        order = Order(
            market_id=1,
            ticker="TEST",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            limit_price=50.0,
            filled_quantity=0,
            remaining_quantity=100,
            status="pending",
            submitted_at=datetime.now(timezone.utc),
        )

        fill_time = datetime.now(timezone.utc)
        order.update_fill(filled_quantity=100, average_price=48.0, filled_at=fill_time)

        assert order.filled_quantity == 100
        assert order.remaining_quantity == 0
        assert order.average_fill_price == 48.0
        assert order.total_cost == 4800.0
        assert order.status == "filled"
        assert order.filled_at == fill_time

    def test_order_update_fill_partial(self) -> None:
        """Test Order.update_fill method for partial fill."""
        from src.shared.models.order import Order

        order = Order(
            market_id=1,
            ticker="TEST",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            limit_price=50.0,
            filled_quantity=0,
            remaining_quantity=100,
            status="pending",
            submitted_at=datetime.now(timezone.utc),
        )

        fill_time = datetime.now(timezone.utc)
        order.update_fill(filled_quantity=50, average_price=48.0, filled_at=fill_time)

        assert order.filled_quantity == 50
        assert order.remaining_quantity == 50
        assert order.status == "partially_filled"


# =============================================================================
# Additional response_models.py coverage
# =============================================================================


class TestResponseModelsAdditional:
    """Additional tests for response_models.py coverage."""

    def test_market_spread_cents_none(self) -> None:
        """Test Market.spread_cents when pricing unavailable."""
        from src.shared.api.response_models import Market

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=None,
            yes_ask=None,
        )

        assert market.spread_cents is None

    def test_market_mid_price_none(self) -> None:
        """Test Market.mid_price when pricing unavailable."""
        from src.shared.api.response_models import Market

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=None,
            yes_ask=None,
        )

        assert market.mid_price is None

    def test_position_average_price(self) -> None:
        """Test Position.average_price property."""
        from src.shared.api.response_models import Position

        position = Position(
            ticker="TEST",
            position=100,
            total_cost=5000,
        )

        assert position.average_price == 50.0

    def test_position_average_price_zero_position(self) -> None:
        """Test Position.average_price when position is 0."""
        from src.shared.api.response_models import Position

        position = Position(
            ticker="TEST",
            position=0,
            total_cost=0,
        )

        assert position.average_price is None

    def test_fill_price_yes_side(self) -> None:
        """Test Fill.price property for yes side."""
        from src.shared.api.response_models import Fill

        fill = Fill(
            fill_id="fill_123",
            order_id="order_123",
            ticker="TEST",
            side="yes",
            action="buy",
            count=10,
            yes_price=50,
            no_price=None,
            created_time=datetime.now(timezone.utc),
        )

        assert fill.price == 50

    def test_fill_price_no_side(self) -> None:
        """Test Fill.price property for no side."""
        from src.shared.api.response_models import Fill

        fill = Fill(
            fill_id="fill_123",
            order_id="order_123",
            ticker="TEST",
            side="no",
            action="buy",
            count=10,
            yes_price=None,
            no_price=50,
            created_time=datetime.now(timezone.utc),
        )

        assert fill.price == 50

    def test_fill_notional_value(self) -> None:
        """Test Fill.notional_value property."""
        from src.shared.api.response_models import Fill

        fill = Fill(
            fill_id="fill_123",
            order_id="order_123",
            ticker="TEST",
            side="yes",
            action="buy",
            count=10,
            yes_price=50,
            created_time=datetime.now(timezone.utc),
        )

        assert fill.notional_value == 500

    def test_order_is_filled_by_status(self) -> None:
        """Test Order.is_filled when determined by status."""
        from src.shared.api.response_models import Order

        order = Order(
            order_id="order_123",
            ticker="TEST",
            side="yes",
            action="buy",
            count=10,
            status="filled",
            created_time=datetime.now(timezone.utc),
        )

        assert order.is_filled is True

    def test_order_is_filled_by_count(self) -> None:
        """Test Order.is_filled when determined by filled_count."""
        from src.shared.api.response_models import Order

        order = Order(
            order_id="order_123",
            ticker="TEST",
            side="yes",
            action="buy",
            count=10,
            filled_count=10,
            status="resting",
            created_time=datetime.now(timezone.utc),
        )

        assert order.is_filled is True

    def test_balance_available_balance(self) -> None:
        """Test Balance.available_balance property."""
        from src.shared.api.response_models import Balance

        balance = Balance(
            balance=10000,
            payout=2000,
        )

        assert balance.available_balance == 8000


# =============================================================================
# Signal validation tests
# =============================================================================


class TestSignalValidation:
    """Tests for Signal validation in signal_generator.py."""

    def test_signal_invalid_confidence_high(self) -> None:
        """Test Signal raises error for confidence > 1."""
        from src.analytics.signal_generator import Signal

        with pytest.raises(ValueError) as exc_info:
            Signal(ticker="TEST", side="yes", confidence=1.5, reason="Test")

        assert "Confidence must be between 0 and 1" in str(exc_info.value)

    def test_signal_invalid_confidence_low(self) -> None:
        """Test Signal raises error for confidence < 0."""
        from src.analytics.signal_generator import Signal

        with pytest.raises(ValueError) as exc_info:
            Signal(ticker="TEST", side="yes", confidence=-0.5, reason="Test")

        assert "Confidence must be between 0 and 1" in str(exc_info.value)

    def test_signal_invalid_side(self) -> None:
        """Test Signal raises error for invalid side."""
        from src.analytics.signal_generator import Signal

        with pytest.raises(ValueError) as exc_info:
            Signal(ticker="TEST", side="invalid", confidence=0.8, reason="Test")

        assert "Side must be 'yes' or 'no'" in str(exc_info.value)
