"""Unit tests for Explanation Generator.

Tests the LLM-based explanation generator for trading signals.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.analytics.signal_generator import Signal
from src.shared.api.response_models import Market
from src.shared.llm.explanation import (
    EXPLANATION_SYSTEM_PROMPT,
    ExplanationGenerator,
    SignalExplanation,
    create_explanation_generator,
)
from src.shared.llm.openrouter import LLMResponse, OpenRouterClient, OpenRouterConfig


class TestSignalExplanation:
    """Tests for SignalExplanation dataclass."""

    def test_explanation_creation(self) -> None:
        """Test creating signal explanation."""
        explanation = SignalExplanation(
            signal_ticker="HIGHNYC-25JAN26-T42",
            explanation="The forecast shows temperatures...",
            weather_summary="Forecast: 45°F",
            market_summary="Strike: 42°F, 55/58¢",
            model_used="anthropic/claude-sonnet-4",
            latency_ms=250.0,
        )

        assert explanation.signal_ticker == "HIGHNYC-25JAN26-T42"
        assert "temperatures" in explanation.explanation
        assert explanation.weather_summary == "Forecast: 45°F"
        assert explanation.model_used == "anthropic/claude-sonnet-4"
        assert explanation.latency_ms == 250.0

    def test_explanation_default_timestamp(self) -> None:
        """Test explanation has default timestamp."""
        explanation = SignalExplanation(
            signal_ticker="TEST",
            explanation="Test",
            weather_summary="Test",
            market_summary="Test",
        )

        assert isinstance(explanation.generated_at, datetime)
        assert explanation.generated_at.tzinfo is not None


class TestExplanationGenerator:
    """Tests for ExplanationGenerator class."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock OpenRouter client."""
        client = MagicMock(spec=OpenRouterClient)
        return client

    @pytest.fixture
    def generator(self, mock_client: MagicMock) -> ExplanationGenerator:
        """Create explanation generator with mock client."""
        return ExplanationGenerator(mock_client)

    @pytest.fixture
    def sample_signal(self) -> Signal:
        """Create sample signal."""
        return Signal(
            ticker="HIGHNYC-25JAN26-T42",
            side="yes",
            confidence=0.75,
            reason="Forecast 45°F above strike 42°F",
            features={
                "forecast_temp": 45.0,
                "strike_price": 42,
                "temp_diff": 3.0,
            },
        )

    @pytest.fixture
    def sample_weather(self) -> dict:
        """Create sample weather data."""
        return {
            "temperature": 45.0,
            "precipitation_probability": 0.2,
            "source": "NWS",
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    @pytest.fixture
    def sample_market(self) -> Market:
        """Create sample market."""
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

    def test_generator_initialization(self, mock_client: MagicMock) -> None:
        """Test generator initialization."""
        generator = ExplanationGenerator(mock_client)
        assert generator._client == mock_client

    def test_generate_success(
        self,
        generator: ExplanationGenerator,
        mock_client: MagicMock,
        sample_signal: Signal,
        sample_weather: dict,
        sample_market: Market,
    ) -> None:
        """Test successful explanation generation."""
        mock_response = LLMResponse(
            content="The weather forecast shows temperatures of 45°F, which is above the strike price of 42°F. Given the tight market spread and good liquidity, a YES position is justified with 75% confidence.",
            model="anthropic/claude-sonnet-4",
            usage={"total_tokens": 50},
            latency_ms=200.0,
        )
        mock_client.chat.return_value = mock_response

        explanation = generator.generate(sample_signal, sample_weather, sample_market)

        assert explanation.signal_ticker == "HIGHNYC-25JAN26-T42"
        assert "45°F" in explanation.explanation
        assert explanation.model_used == "anthropic/claude-sonnet-4"
        assert explanation.latency_ms == 200.0

        # Verify LLM was called
        mock_client.chat.assert_called_once()
        call_args = mock_client.chat.call_args
        assert call_args[1]["system_prompt"] == EXPLANATION_SYSTEM_PROMPT

    def test_generate_with_weather_summary(
        self,
        generator: ExplanationGenerator,
        mock_client: MagicMock,
        sample_signal: Signal,
        sample_weather: dict,
        sample_market: Market,
    ) -> None:
        """Test that weather summary is generated correctly."""
        mock_response = LLMResponse(
            content="Explanation text here.",
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        explanation = generator.generate(sample_signal, sample_weather, sample_market)

        assert "45.0°F" in explanation.weather_summary
        assert "20%" in explanation.weather_summary  # precipitation

    def test_generate_with_market_summary(
        self,
        generator: ExplanationGenerator,
        mock_client: MagicMock,
        sample_signal: Signal,
        sample_weather: dict,
        sample_market: Market,
    ) -> None:
        """Test that market summary is generated correctly."""
        mock_response = LLMResponse(
            content="Explanation text here.",
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        explanation = generator.generate(sample_signal, sample_weather, sample_market)

        assert "42.0°F" in explanation.market_summary
        assert "55/58¢" in explanation.market_summary

    def test_generate_fallback_on_error(
        self,
        generator: ExplanationGenerator,
        mock_client: MagicMock,
        sample_signal: Signal,
        sample_weather: dict,
        sample_market: Market,
    ) -> None:
        """Test fallback explanation when LLM fails."""
        mock_client.chat.side_effect = Exception("API error")

        explanation = generator.generate(sample_signal, sample_weather, sample_market)

        assert explanation.signal_ticker == "HIGHNYC-25JAN26-T42"
        assert "LLM explanation unavailable" in explanation.explanation
        assert explanation.model_used == "fallback"
        assert explanation.latency_ms == 0.0

    def test_generate_prompt_content(
        self,
        generator: ExplanationGenerator,
        mock_client: MagicMock,
        sample_signal: Signal,
        sample_weather: dict,
        sample_market: Market,
    ) -> None:
        """Test that prompt contains required information."""
        mock_response = LLMResponse(
            content="Test response",
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        generator.generate(sample_signal, sample_weather, sample_market)

        # Get the prompt that was sent
        call_args = mock_client.chat.call_args
        prompt = call_args[1]["prompt"]

        # Verify prompt contains key information
        assert "HIGHNYC-25JAN26-T42" in prompt
        assert "YES" in prompt  # side
        assert "75%" in prompt  # confidence
        assert "45" in prompt  # temperature
        assert "42" in prompt  # strike

    def test_generate_with_missing_weather_data(
        self,
        generator: ExplanationGenerator,
        mock_client: MagicMock,
        sample_signal: Signal,
        sample_market: Market,
    ) -> None:
        """Test generation with missing weather data."""
        mock_response = LLMResponse(
            content="Limited weather data available.",
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        weather_data = {"source": "NWS"}  # Missing temperature
        explanation = generator.generate(sample_signal, weather_data, sample_market)

        assert explanation.weather_summary == "Forecast: N/A°F"

    def test_generate_with_missing_market_data(
        self,
        generator: ExplanationGenerator,
        mock_client: MagicMock,
        sample_signal: Signal,
        sample_weather: dict,
    ) -> None:
        """Test generation with missing market data."""
        mock_response = LLMResponse(
            content="Market data limited.",
            model="test-model",
            latency_ms=100.0,
        )
        mock_client.chat.return_value = mock_response

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=None,
            yes_ask=None,
            volume=0,
            open_interest=0,
            strike_price=None,
        )

        explanation = generator.generate(sample_signal, sample_weather, market)

        assert explanation.market_summary == "Strike: None°F"


class TestCreateExplanationGenerator:
    """Tests for factory function."""

    def test_create_with_api_key(self) -> None:
        """Test creating generator with API key."""
        with patch("src.shared.llm.explanation.OpenRouterClient"):
            generator = create_explanation_generator(api_key="test-key")
            assert isinstance(generator, ExplanationGenerator)

    def test_create_from_environment(self) -> None:
        """Test creating generator from environment."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            with patch("src.shared.llm.explanation.OpenRouterClient"):
                generator = create_explanation_generator()
                assert isinstance(generator, ExplanationGenerator)

    def test_create_without_key_raises(self) -> None:
        """Test that missing API key raises error."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                create_explanation_generator()

            assert "API key required" in str(exc_info.value)


class TestExplanationSystemPrompt:
    """Tests for system prompt content."""

    def test_system_prompt_contains_guidelines(self) -> None:
        """Test system prompt has required guidelines."""
        assert "factual" in EXPLANATION_SYSTEM_PROMPT.lower()
        assert "150 words" in EXPLANATION_SYSTEM_PROMPT
        assert "audit" in EXPLANATION_SYSTEM_PROMPT.lower()

    def test_system_prompt_emphasizes_advisory_only(self) -> None:
        """Test system prompt emphasizes advisory nature."""
        prompt_lower = EXPLANATION_SYSTEM_PROMPT.lower()
        assert "trading decision has already been made" in prompt_lower
        assert "transparency" in prompt_lower or "audit" in prompt_lower
