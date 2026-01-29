"""Unit tests for Anomaly Classifier.

Tests the LLM-based anomaly classifier for market conditions.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.api.response_models import Market
from src.shared.llm.anomaly import (
    ANOMALY_SYSTEM_PROMPT,
    AnomalyClassification,
    AnomalyClassificationResult,
    AnomalyClassifier,
    AnomalyType,
    create_anomaly_classifier,
)
from src.shared.llm.openrouter import LLMResponse, OpenRouterClient


class TestAnomalyType:
    """Tests for AnomalyType enum."""

    def test_anomaly_types(self) -> None:
        """Test all anomaly types exist."""
        assert AnomalyType.WIDE_SPREAD.value == "wide_spread"
        assert AnomalyType.LOW_LIQUIDITY.value == "low_liquidity"
        assert AnomalyType.FORECAST_DISAGREEMENT.value == "forecast_disagreement"
        assert AnomalyType.PRICE_MISMATCH.value == "price_mismatch"
        assert AnomalyType.VOLUME_SPIKE.value == "volume_spike"
        assert AnomalyType.MARKET_HALTED.value == "market_halted"
        assert AnomalyType.DATA_STALE.value == "data_stale"
        assert AnomalyType.UNKNOWN.value == "unknown"


class TestAnomalyClassificationResult:
    """Tests for AnomalyClassificationResult enum."""

    def test_classification_results(self) -> None:
        """Test all classification results exist."""
        assert AnomalyClassificationResult.NORMAL.value == "normal"
        assert AnomalyClassificationResult.SUSPICIOUS.value == "suspicious"
        assert AnomalyClassificationResult.ALERT.value == "alert"


class TestAnomalyClassification:
    """Tests for AnomalyClassification dataclass."""

    def test_classification_creation(self) -> None:
        """Test creating anomaly classification."""
        classification = AnomalyClassification(
            ticker="HIGHNYC-25JAN26-T42",
            classification=AnomalyClassificationResult.SUSPICIOUS,
            anomaly_type=AnomalyType.WIDE_SPREAD,
            reason="Spread of 8¢ exceeds threshold",
            confidence=0.9,
            raw_data={"spread_cents": 8},
            model_used="anthropic/claude-sonnet-4",
            latency_ms=150.0,
        )

        assert classification.ticker == "HIGHNYC-25JAN26-T42"
        assert classification.classification == AnomalyClassificationResult.SUSPICIOUS
        assert classification.anomaly_type == AnomalyType.WIDE_SPREAD
        assert classification.confidence == 0.9
        assert classification.latency_ms == 150.0

    def test_classification_default_timestamp(self) -> None:
        """Test classification has default timestamp."""
        classification = AnomalyClassification(
            ticker="TEST",
            classification=AnomalyClassificationResult.NORMAL,
            anomaly_type=AnomalyType.UNKNOWN,
            reason="No issues",
            confidence=1.0,
        )

        assert isinstance(classification.classified_at, datetime)
        assert classification.classified_at.tzinfo is not None


class TestAnomalyClassifier:
    """Tests for AnomalyClassifier class."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock OpenRouter client."""
        return MagicMock(spec=OpenRouterClient)

    @pytest.fixture
    def classifier(self, mock_client: MagicMock) -> AnomalyClassifier:
        """Create anomaly classifier with mock client."""
        return AnomalyClassifier(mock_client)

    @pytest.fixture
    def normal_market(self) -> Market:
        """Create normal market conditions."""
        return Market(
            ticker="HIGHNYC-25JAN26-T42",
            event_ticker="HIGHNYC-25JAN26",
            title="NYC High Temp ≥42°F",
            status="open",
            yes_bid=55,
            yes_ask=58,
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

    @pytest.fixture
    def normal_weather(self) -> dict:
        """Create normal weather data."""
        return {
            "temperature": 45.0,
            "precipitation_probability": 0.2,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_classifier_initialization(self, mock_client: MagicMock) -> None:
        """Test classifier initialization."""
        classifier = AnomalyClassifier(mock_client)
        assert classifier._client == mock_client

    def test_classify_normal_conditions(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_market: Market,
        normal_weather: dict,
    ) -> None:
        """Test classification of normal conditions."""
        result = classifier.classify(normal_market, normal_weather)

        assert result.classification == AnomalyClassificationResult.NORMAL
        assert result.reason == "No anomalies detected"
        assert result.confidence == 1.0

        # LLM should not be called for NORMAL
        mock_client.chat.assert_not_called()

    def test_classify_wide_spread(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_weather: dict,
    ) -> None:
        """Test detection of wide spread."""
        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=50,
            yes_ask=58,  # 8¢ spread
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        # Mock LLM response
        mock_response = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "wide_spread", "reason": "Spread indicates low confidence", "confidence": 0.85}',
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        result = classifier.classify(market, normal_weather)

        assert result.classification == AnomalyClassificationResult.SUSPICIOUS
        assert result.anomaly_type == AnomalyType.WIDE_SPREAD

    def test_classify_low_volume(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_weather: dict,
    ) -> None:
        """Test detection of low volume."""
        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=55,
            yes_ask=58,
            volume=50,  # Below threshold
            open_interest=1500,
            strike_price=42,
        )

        mock_response = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "low_liquidity", "reason": "Low volume", "confidence": 0.8}',
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        result = classifier.classify(market, normal_weather)

        assert result.anomaly_type == AnomalyType.LOW_LIQUIDITY

    def test_classify_low_open_interest(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_weather: dict,
    ) -> None:
        """Test detection of low open interest."""
        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=55,
            yes_ask=58,
            volume=500,
            open_interest=200,  # Below threshold
            strike_price=42,
        )

        mock_response = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "low_liquidity", "reason": "Low OI", "confidence": 0.8}',
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        result = classifier.classify(market, normal_weather)

        assert result.anomaly_type == AnomalyType.LOW_LIQUIDITY

    def test_classify_market_halted(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_weather: dict,
    ) -> None:
        """Test detection of halted market."""
        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="halted",
            yes_bid=55,
            yes_ask=58,
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        # Halted should trigger ALERT immediately
        mock_response = LLMResponse(
            content='{"classification": "ALERT", "anomaly_type": "market_halted", "reason": "Market halted", "confidence": 1.0}',
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        result = classifier.classify(market, normal_weather)

        assert result.classification == AnomalyClassificationResult.ALERT
        assert result.anomaly_type == AnomalyType.MARKET_HALTED

    def test_classify_stale_data(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_market: Market,
    ) -> None:
        """Test detection of stale weather data."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        weather = {
            "temperature": 45.0,
            "captured_at": old_time.isoformat(),
        }

        mock_response = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "data_stale", "reason": "Data is old", "confidence": 0.8}',
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        result = classifier.classify(normal_market, weather)

        assert result.anomaly_type == AnomalyType.DATA_STALE

    def test_classify_forecast_disagreement(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_market: Market,
    ) -> None:
        """Test detection of forecast disagreement."""
        primary = {"temperature": 45.0, "captured_at": datetime.now(timezone.utc).isoformat()}
        secondary = {"temperature": 52.0}  # 7°F difference

        mock_response = LLMResponse(
            content='{"classification": "SUSPICIOUS", "anomaly_type": "forecast_disagreement", "reason": "Forecasts differ by 7F", "confidence": 0.75}',
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        result = classifier.classify(normal_market, primary, secondary)

        assert result.anomaly_type == AnomalyType.FORECAST_DISAGREEMENT

    def test_classify_llm_error_fallback(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_weather: dict,
    ) -> None:
        """Test fallback to rule-based when LLM fails."""
        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=50,
            yes_ask=58,  # Wide spread
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        mock_client.chat.side_effect = Exception("LLM error")

        result = classifier.classify(market, normal_weather)

        # Should still detect wide spread via rules
        assert result.anomaly_type == AnomalyType.WIDE_SPREAD
        assert result.classification == AnomalyClassificationResult.SUSPICIOUS

    def test_classify_llm_invalid_json(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_weather: dict,
    ) -> None:
        """Test handling of invalid JSON from LLM."""
        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=50,
            yes_ask=58,
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        mock_response = LLMResponse(
            content="This is not valid JSON",
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        result = classifier.classify(market, normal_weather)

        # Should fall back to rule-based
        assert result.anomaly_type == AnomalyType.WIDE_SPREAD

    def test_classify_llm_json_in_code_block(
        self,
        classifier: AnomalyClassifier,
        mock_client: MagicMock,
        normal_weather: dict,
    ) -> None:
        """Test parsing JSON from markdown code block."""
        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=50,
            yes_ask=58,
            volume=500,
            open_interest=1500,
            strike_price=42,
        )

        mock_response = LLMResponse(
            content='```json\n{"classification": "ALERT", "anomaly_type": "wide_spread", "reason": "Severe spread issue", "confidence": 0.95}\n```',
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        result = classifier.classify(market, normal_weather)

        assert result.classification == AnomalyClassificationResult.ALERT
        assert result.reason == "Severe spread issue"


class TestCreateAnomalyClassifier:
    """Tests for factory function."""

    def test_create_with_api_key(self) -> None:
        """Test creating classifier with API key."""
        with patch("src.shared.llm.anomaly.OpenRouterClient"):
            classifier = create_anomaly_classifier(api_key="test-key")
            assert isinstance(classifier, AnomalyClassifier)

    def test_create_from_environment(self) -> None:
        """Test creating classifier from environment."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            with patch("src.shared.llm.anomaly.OpenRouterClient"):
                classifier = create_anomaly_classifier()
                assert isinstance(classifier, AnomalyClassifier)

    def test_create_without_key_raises(self) -> None:
        """Test that missing API key raises error."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                create_anomaly_classifier()

            assert "API key required" in str(exc_info.value)


class TestAnomalySystemPrompt:
    """Tests for system prompt content."""

    def test_system_prompt_contains_classifications(self) -> None:
        """Test system prompt defines classifications."""
        assert "NORMAL" in ANOMALY_SYSTEM_PROMPT
        assert "SUSPICIOUS" in ANOMALY_SYSTEM_PROMPT
        assert "ALERT" in ANOMALY_SYSTEM_PROMPT

    def test_system_prompt_contains_anomaly_types(self) -> None:
        """Test system prompt defines anomaly types."""
        prompt_lower = ANOMALY_SYSTEM_PROMPT.lower()
        assert "wide spread" in prompt_lower
        assert "low liquidity" in prompt_lower
        assert "forecast disagreement" in prompt_lower

    def test_system_prompt_requests_json(self) -> None:
        """Test system prompt requests JSON response."""
        assert "JSON" in ANOMALY_SYSTEM_PROMPT
        assert "classification" in ANOMALY_SYSTEM_PROMPT
        assert "reason" in ANOMALY_SYSTEM_PROMPT


class TestAnomalyClassifierThresholds:
    """Tests for anomaly detection thresholds."""

    def test_wide_spread_threshold(self) -> None:
        """Test wide spread threshold constant."""
        assert AnomalyClassifier.WIDE_SPREAD_THRESHOLD == 5

    def test_low_volume_threshold(self) -> None:
        """Test low volume threshold constant."""
        assert AnomalyClassifier.LOW_VOLUME_THRESHOLD == 100

    def test_low_oi_threshold(self) -> None:
        """Test low open interest threshold constant."""
        assert AnomalyClassifier.LOW_OI_THRESHOLD == 500

    def test_stale_data_threshold(self) -> None:
        """Test stale data threshold constant."""
        assert AnomalyClassifier.STALE_DATA_MINUTES == 15
