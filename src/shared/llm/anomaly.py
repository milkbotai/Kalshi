"""Anomaly classifier for unusual market conditions.

Uses LLM to classify market anomalies such as wide spreads,
low liquidity, or forecast disagreements. Classifications
are stored for monitoring and dashboard display.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.shared.api.response_models import Market
from src.shared.config.logging import get_logger
from src.shared.llm.openrouter import LLMResponse, OpenRouterClient, OpenRouterConfig

logger = get_logger(__name__)


class AnomalyType(Enum):
    """Types of detected anomalies."""

    WIDE_SPREAD = "wide_spread"
    LOW_LIQUIDITY = "low_liquidity"
    FORECAST_DISAGREEMENT = "forecast_disagreement"
    PRICE_MISMATCH = "price_mismatch"
    VOLUME_SPIKE = "volume_spike"
    MARKET_HALTED = "market_halted"
    DATA_STALE = "data_stale"
    UNKNOWN = "unknown"


class AnomalyClassificationResult(Enum):
    """Classification results for anomaly severity."""

    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    ALERT = "alert"


# System prompt for anomaly classification
ANOMALY_SYSTEM_PROMPT = """You are an expert financial market analyst specializing in weather derivatives.

Your role is to classify unusual market conditions and identify potential anomalies. You analyze market data, weather forecasts, and trading patterns to detect irregularities.

Classification Guidelines:
- NORMAL: Standard market conditions, no concerns
- SUSPICIOUS: Unusual but not necessarily problematic, warrants monitoring
- ALERT: Significant anomaly that requires immediate attention

Anomaly Types to Consider:
1. Wide Spread (>5 cents): May indicate low confidence or thin liquidity
2. Low Liquidity: Volume < 100 or OI < 500 may cause execution issues
3. Forecast Disagreement: When primary and secondary forecasts differ significantly
4. Price Mismatch: Market price seems inconsistent with weather probability
5. Volume Spike: Unusual trading activity compared to historical norms
6. Data Stale: Weather data older than 15 minutes

Respond with a JSON object containing:
- classification: "NORMAL", "SUSPICIOUS", or "ALERT"
- anomaly_type: The primary anomaly type detected
- reason: Brief explanation (1-2 sentences)
- confidence: Your confidence in the classification (0.0-1.0)"""


@dataclass
class AnomalyClassification:
    """Anomaly classification result.

    Attributes:
        ticker: Market ticker being classified
        classification: Classification result (NORMAL/SUSPICIOUS/ALERT)
        anomaly_type: Type of anomaly detected
        reason: Explanation for the classification
        confidence: Confidence in the classification (0.0-1.0)
        raw_data: Input data used for classification
        classified_at: When classification was made
        model_used: LLM model used
        latency_ms: Classification latency
    """

    ticker: str
    classification: AnomalyClassificationResult
    anomaly_type: AnomalyType
    reason: str
    confidence: float
    raw_data: dict[str, Any] = field(default_factory=dict)
    classified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model_used: str = ""
    latency_ms: float = 0.0


class AnomalyClassifier:
    """Classifies unusual market conditions using LLM.

    Analyzes market and weather data to detect anomalies like
    wide spreads, low liquidity, and forecast disagreements.
    Classifications are stored in analytics.anomalies table.

    Example:
        classifier = AnomalyClassifier(openrouter_client)
        result = classifier.classify(market, weather_data)
        if result.classification == AnomalyClassificationResult.ALERT:
            send_alert(result)
    """

    # Thresholds for rule-based pre-classification
    WIDE_SPREAD_THRESHOLD = 5  # cents
    LOW_VOLUME_THRESHOLD = 100
    LOW_OI_THRESHOLD = 500
    STALE_DATA_MINUTES = 15

    def __init__(self, client: OpenRouterClient) -> None:
        """Initialize anomaly classifier.

        Args:
            client: OpenRouter client for LLM access
        """
        self._client = client
        logger.info("anomaly_classifier_initialized")

    def classify(
        self,
        market: Market,
        weather_data: dict[str, Any],
        secondary_forecast: dict[str, Any] | None = None,
    ) -> AnomalyClassification:
        """Classify market conditions for anomalies.

        Args:
            market: Market data to analyze
            weather_data: Primary weather forecast data
            secondary_forecast: Optional secondary forecast for comparison

        Returns:
            AnomalyClassification with result and explanation
        """
        # First, apply rule-based detection for obvious anomalies
        rule_based = self._rule_based_detection(market, weather_data, secondary_forecast)

        # If rule-based detection finds ALERT, use LLM to confirm and explain
        # If NORMAL, skip LLM to save costs
        # If SUSPICIOUS, use LLM for deeper analysis
        if rule_based.classification == AnomalyClassificationResult.NORMAL:
            logger.debug("anomaly_classification_normal", ticker=market.ticker)
            return rule_based

        # Use LLM for SUSPICIOUS and ALERT cases
        try:
            llm_result = self._llm_classification(
                market, weather_data, secondary_forecast, rule_based
            )
            logger.info(
                "anomaly_classified",
                ticker=market.ticker,
                classification=llm_result.classification.value,
                anomaly_type=llm_result.anomaly_type.value,
            )
            return llm_result

        except Exception as e:
            logger.error(
                "anomaly_classification_failed",
                ticker=market.ticker,
                error=str(e),
            )
            # Fall back to rule-based result
            return rule_based

    def _rule_based_detection(
        self,
        market: Market,
        weather_data: dict[str, Any],
        secondary_forecast: dict[str, Any] | None = None,
    ) -> AnomalyClassification:
        """Apply rule-based anomaly detection.

        Args:
            market: Market data
            weather_data: Weather data
            secondary_forecast: Optional secondary forecast

        Returns:
            Initial classification based on rules
        """
        raw_data = {
            "market_ticker": market.ticker,
            "spread_cents": market.spread_cents,
            "volume": market.volume,
            "open_interest": market.open_interest,
            "status": market.status,
        }

        # Check for market halted
        if market.status != "open":
            return AnomalyClassification(
                ticker=market.ticker,
                classification=AnomalyClassificationResult.ALERT,
                anomaly_type=AnomalyType.MARKET_HALTED,
                reason=f"Market is {market.status}, not open for trading",
                confidence=1.0,
                raw_data=raw_data,
            )

        # Check for wide spread
        if market.spread_cents and market.spread_cents > self.WIDE_SPREAD_THRESHOLD:
            return AnomalyClassification(
                ticker=market.ticker,
                classification=AnomalyClassificationResult.SUSPICIOUS,
                anomaly_type=AnomalyType.WIDE_SPREAD,
                reason=f"Spread of {market.spread_cents}¢ exceeds threshold of {self.WIDE_SPREAD_THRESHOLD}¢",
                confidence=0.9,
                raw_data=raw_data,
            )

        # Check for low liquidity
        if market.volume < self.LOW_VOLUME_THRESHOLD:
            return AnomalyClassification(
                ticker=market.ticker,
                classification=AnomalyClassificationResult.SUSPICIOUS,
                anomaly_type=AnomalyType.LOW_LIQUIDITY,
                reason=f"Volume of {market.volume} below threshold of {self.LOW_VOLUME_THRESHOLD}",
                confidence=0.85,
                raw_data=raw_data,
            )

        if market.open_interest < self.LOW_OI_THRESHOLD:
            return AnomalyClassification(
                ticker=market.ticker,
                classification=AnomalyClassificationResult.SUSPICIOUS,
                anomaly_type=AnomalyType.LOW_LIQUIDITY,
                reason=f"Open interest of {market.open_interest} below threshold of {self.LOW_OI_THRESHOLD}",
                confidence=0.85,
                raw_data=raw_data,
            )

        # Check for stale data
        captured_at = weather_data.get("captured_at")
        if captured_at:
            from datetime import datetime as dt

            if isinstance(captured_at, str):
                try:
                    captured_at = dt.fromisoformat(captured_at.replace("Z", "+00:00"))
                except ValueError:
                    pass

            if isinstance(captured_at, dt):
                age_minutes = (
                    datetime.now(timezone.utc) - captured_at
                ).total_seconds() / 60
                if age_minutes > self.STALE_DATA_MINUTES:
                    return AnomalyClassification(
                        ticker=market.ticker,
                        classification=AnomalyClassificationResult.SUSPICIOUS,
                        anomaly_type=AnomalyType.DATA_STALE,
                        reason=f"Weather data is {age_minutes:.0f} minutes old (threshold: {self.STALE_DATA_MINUTES})",
                        confidence=0.8,
                        raw_data=raw_data,
                    )

        # Check for forecast disagreement
        if secondary_forecast:
            primary_temp = weather_data.get("temperature")
            secondary_temp = secondary_forecast.get("temperature")

            if primary_temp is not None and secondary_temp is not None:
                temp_diff = abs(primary_temp - secondary_temp)
                if temp_diff > 5:  # More than 5°F difference
                    return AnomalyClassification(
                        ticker=market.ticker,
                        classification=AnomalyClassificationResult.SUSPICIOUS,
                        anomaly_type=AnomalyType.FORECAST_DISAGREEMENT,
                        reason=f"Primary forecast ({primary_temp}°F) differs from secondary ({secondary_temp}°F) by {temp_diff}°F",
                        confidence=0.75,
                        raw_data=raw_data,
                    )

        # All checks passed - normal conditions
        return AnomalyClassification(
            ticker=market.ticker,
            classification=AnomalyClassificationResult.NORMAL,
            anomaly_type=AnomalyType.UNKNOWN,
            reason="No anomalies detected",
            confidence=1.0,
            raw_data=raw_data,
        )

    def _llm_classification(
        self,
        market: Market,
        weather_data: dict[str, Any],
        secondary_forecast: dict[str, Any] | None,
        rule_based: AnomalyClassification,
    ) -> AnomalyClassification:
        """Use LLM to classify and explain anomaly.

        Args:
            market: Market data
            weather_data: Weather data
            secondary_forecast: Optional secondary forecast
            rule_based: Initial rule-based classification

        Returns:
            LLM-enhanced classification
        """
        prompt = self._build_prompt(market, weather_data, secondary_forecast, rule_based)

        response = self._client.chat(
            prompt=prompt,
            system_prompt=ANOMALY_SYSTEM_PROMPT,
            max_tokens=256,
            temperature=0.2,
        )

        return self._parse_response(response, market, rule_based)

    def _build_prompt(
        self,
        market: Market,
        weather_data: dict[str, Any],
        secondary_forecast: dict[str, Any] | None,
        rule_based: AnomalyClassification,
    ) -> str:
        """Build LLM prompt for anomaly classification.

        Args:
            market: Market data
            weather_data: Weather data
            secondary_forecast: Optional secondary forecast
            rule_based: Initial rule-based detection

        Returns:
            Formatted prompt
        """
        # Format market data
        bid = f"{market.yes_bid}¢" if market.yes_bid else "N/A"
        ask = f"{market.yes_ask}¢" if market.yes_ask else "N/A"
        spread = f"{market.spread_cents}¢" if market.spread_cents else "N/A"

        # Format weather data
        primary_temp = weather_data.get("temperature", "N/A")

        secondary_section = ""
        if secondary_forecast:
            secondary_temp = secondary_forecast.get("temperature", "N/A")
            secondary_section = f"\nSecondary Forecast: {secondary_temp}°F"

        prompt = f"""Analyze this market for anomalies:

MARKET DATA:
- Ticker: {market.ticker}
- Status: {market.status}
- Bid/Ask: {bid}/{ask}
- Spread: {spread}
- Volume: {market.volume:,}
- Open Interest: {market.open_interest:,}
- Strike Price: {market.strike_price or 'N/A'}°F

WEATHER DATA:
- Primary Forecast: {primary_temp}°F{secondary_section}

INITIAL DETECTION:
- Detected Anomaly Type: {rule_based.anomaly_type.value}
- Initial Classification: {rule_based.classification.value}
- Reason: {rule_based.reason}

Based on this data, provide your classification. Respond with valid JSON:
{{"classification": "NORMAL|SUSPICIOUS|ALERT", "anomaly_type": "{rule_based.anomaly_type.value}", "reason": "your explanation", "confidence": 0.0-1.0}}"""

        return prompt

    def _parse_response(
        self,
        response: LLMResponse,
        market: Market,
        rule_based: AnomalyClassification,
    ) -> AnomalyClassification:
        """Parse LLM response into AnomalyClassification.

        Args:
            response: LLM response
            market: Market data
            rule_based: Fallback classification

        Returns:
            Parsed classification
        """
        import json

        try:
            # Try to extract JSON from response
            content = response.content.strip()

            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            # Parse classification
            classification_str = data.get("classification", "SUSPICIOUS").upper()
            if classification_str == "NORMAL":
                classification = AnomalyClassificationResult.NORMAL
            elif classification_str == "ALERT":
                classification = AnomalyClassificationResult.ALERT
            else:
                classification = AnomalyClassificationResult.SUSPICIOUS

            # Parse anomaly type
            anomaly_type_str = data.get("anomaly_type", rule_based.anomaly_type.value)
            try:
                anomaly_type = AnomalyType(anomaly_type_str)
            except ValueError:
                anomaly_type = rule_based.anomaly_type

            # Parse other fields
            reason = data.get("reason", rule_based.reason)
            confidence = float(data.get("confidence", rule_based.confidence))
            confidence = max(0.0, min(1.0, confidence))

            return AnomalyClassification(
                ticker=market.ticker,
                classification=classification,
                anomaly_type=anomaly_type,
                reason=reason,
                confidence=confidence,
                raw_data=rule_based.raw_data,
                model_used=response.model,
                latency_ms=response.latency_ms,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "anomaly_response_parse_failed",
                error=str(e),
                content=response.content[:200],
            )
            # Return rule-based result with LLM metadata
            rule_based.model_used = response.model
            rule_based.latency_ms = response.latency_ms
            return rule_based


def create_anomaly_classifier(api_key: str | None = None) -> AnomalyClassifier:
    """Factory function to create AnomalyClassifier.

    Args:
        api_key: Optional OpenRouter API key

    Returns:
        Configured AnomalyClassifier instance
    """
    import os

    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OpenRouter API key required for anomaly classifier")

    config = OpenRouterConfig(api_key=key)
    client = OpenRouterClient(config)
    return AnomalyClassifier(client)
