"""Explanation generator for trading signals.

Generates human-readable explanations for trading signals using LLM.
Explanations are advisory only and never affect trading decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.analytics.signal_generator import Signal
from src.shared.api.response_models import Market
from src.shared.config.logging import get_logger
from src.shared.llm.openrouter import LLMResponse, OpenRouterClient, OpenRouterConfig

logger = get_logger(__name__)

# System prompt for explanation generation
EXPLANATION_SYSTEM_PROMPT = """You are an expert weather analyst explaining trading decisions for a weather derivatives trading platform.

Your role is to generate clear, concise explanations for trading signals. These explanations help human operators understand why the system made specific trading decisions.

Guidelines:
1. Be factual and objective - focus on data, not speculation
2. Keep explanations under 150 words
3. Structure as: Weather conditions -> Market analysis -> Trading rationale
4. Use plain language accessible to non-meteorologists
5. Never include investment advice or recommendations
6. Acknowledge uncertainty when present in the data

The trading decision has already been made. Your explanation is for transparency and audit purposes only."""


@dataclass
class SignalExplanation:
    """Explanation for a trading signal.

    Attributes:
        signal_ticker: The ticker for the signal
        explanation: Human-readable explanation text
        weather_summary: Brief weather conditions summary
        market_summary: Brief market conditions summary
        generated_at: When explanation was generated
        model_used: LLM model that generated explanation
        latency_ms: Time to generate explanation
    """

    signal_ticker: str
    explanation: str
    weather_summary: str
    market_summary: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model_used: str = ""
    latency_ms: float = 0.0


class ExplanationGenerator:
    """Generates human-readable explanations for trading signals.

    Uses LLM to create clear explanations that help operators understand
    trading decisions. Explanations are purely advisory and stored in
    analytics.signal_explanations table.

    Example:
        generator = ExplanationGenerator(openrouter_client)
        explanation = generator.generate(signal, weather_data, market)
        print(explanation.explanation)
    """

    def __init__(self, client: OpenRouterClient) -> None:
        """Initialize explanation generator.

        Args:
            client: OpenRouter client for LLM access
        """
        self._client = client
        logger.info("explanation_generator_initialized")

    def generate(
        self,
        signal: Signal,
        weather_data: dict[str, Any],
        market: Market,
    ) -> SignalExplanation:
        """Generate explanation for a trading signal.

        Args:
            signal: Trading signal to explain
            weather_data: Weather data used for signal
            market: Market data for the signal

        Returns:
            SignalExplanation with generated text

        Note:
            Explanation never affects trading decision (advisory only).
        """
        prompt = self._build_prompt(signal, weather_data, market)

        try:
            response = self._client.chat(
                prompt=prompt,
                system_prompt=EXPLANATION_SYSTEM_PROMPT,
                max_tokens=512,
                temperature=0.3,
            )

            explanation = self._parse_response(response, signal, weather_data, market)

            logger.info(
                "explanation_generated",
                ticker=signal.ticker,
                latency_ms=response.latency_ms,
            )

            return explanation

        except Exception as e:
            logger.error(
                "explanation_generation_failed",
                ticker=signal.ticker,
                error=str(e),
            )
            # Return fallback explanation
            return self._fallback_explanation(signal, weather_data, market)

    def _build_prompt(
        self,
        signal: Signal,
        weather_data: dict[str, Any],
        market: Market,
    ) -> str:
        """Build LLM prompt from signal and data.

        Args:
            signal: Trading signal
            weather_data: Weather data dictionary
            market: Market data

        Returns:
            Formatted prompt string
        """
        # Extract weather details
        temp = weather_data.get("temperature", "N/A")
        precip_prob = weather_data.get("precipitation_probability", "N/A")
        forecast_source = weather_data.get("source", "NWS")

        # Format precipitation probability
        if isinstance(precip_prob, (int, float)):
            precip_str = f"{precip_prob:.0%}"
        else:
            precip_str = str(precip_prob)

        # Format market details
        bid = f"{market.yes_bid}¢" if market.yes_bid else "N/A"
        ask = f"{market.yes_ask}¢" if market.yes_ask else "N/A"
        spread = f"{market.spread_cents}¢" if market.spread_cents else "N/A"

        prompt = f"""Generate an explanation for this trading signal:

TRADING SIGNAL:
- Ticker: {signal.ticker}
- Side: {signal.side.upper()}
- Confidence: {signal.confidence:.0%}
- Decision Reason: {signal.reason}

WEATHER DATA:
- Forecast Temperature: {temp}°F
- Precipitation Probability: {precip_str}
- Data Source: {forecast_source}

MARKET DATA:
- Strike Price: {market.strike_price or 'N/A'}°F
- Bid/Ask: {bid}/{ask}
- Spread: {spread}
- Volume: {market.volume:,}
- Status: {market.status}

Please provide a clear explanation of why this trading signal was generated, covering:
1. Current weather conditions and forecast
2. Market pricing and liquidity
3. The trading rationale (why this side at this confidence level)"""

        return prompt

    def _parse_response(
        self,
        response: LLMResponse,
        signal: Signal,
        weather_data: dict[str, Any],
        market: Market,
    ) -> SignalExplanation:
        """Parse LLM response into SignalExplanation.

        Args:
            response: LLM response
            signal: Original signal
            weather_data: Weather data
            market: Market data

        Returns:
            Parsed SignalExplanation
        """
        # Build summaries from raw data
        temp = weather_data.get("temperature", "N/A")
        weather_summary = f"Forecast: {temp}°F"

        if "precipitation_probability" in weather_data:
            prob = weather_data["precipitation_probability"]
            if isinstance(prob, (int, float)):
                weather_summary += f", {prob:.0%} precip chance"

        market_summary = f"Strike: {market.strike_price}°F"
        if market.yes_bid and market.yes_ask:
            market_summary += f", {market.yes_bid}/{market.yes_ask}¢"

        return SignalExplanation(
            signal_ticker=signal.ticker,
            explanation=response.content.strip(),
            weather_summary=weather_summary,
            market_summary=market_summary,
            model_used=response.model,
            latency_ms=response.latency_ms,
        )

    def _fallback_explanation(
        self,
        signal: Signal,
        weather_data: dict[str, Any],
        market: Market,
    ) -> SignalExplanation:
        """Generate fallback explanation when LLM fails.

        Args:
            signal: Trading signal
            weather_data: Weather data
            market: Market data

        Returns:
            Basic SignalExplanation without LLM
        """
        temp = weather_data.get("temperature", "N/A")
        weather_summary = f"Forecast: {temp}°F"

        market_summary = f"Strike: {market.strike_price}°F"

        explanation = (
            f"Trading signal generated for {signal.ticker}. "
            f"Decision: {signal.side.upper()} with {signal.confidence:.0%} confidence. "
            f"Reason: {signal.reason}. "
            f"(Note: LLM explanation unavailable)"
        )

        return SignalExplanation(
            signal_ticker=signal.ticker,
            explanation=explanation,
            weather_summary=weather_summary,
            market_summary=market_summary,
            model_used="fallback",
            latency_ms=0.0,
        )


def create_explanation_generator(api_key: str | None = None) -> ExplanationGenerator:
    """Factory function to create ExplanationGenerator.

    Args:
        api_key: Optional OpenRouter API key

    Returns:
        Configured ExplanationGenerator instance
    """
    import os

    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OpenRouter API key required for explanation generator")

    config = OpenRouterConfig(api_key=key)
    client = OpenRouterClient(config)
    return ExplanationGenerator(client)
