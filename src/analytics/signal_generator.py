"""Signal generator for trading decisions.

Generates trading signals based on weather data and market conditions.
Combines multiple signal types with confidence scoring.
"""

from dataclasses import dataclass
from typing import Any

from src.shared.api.response_models import Market
from src.shared.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Signal:
    """Trading signal with confidence and reasoning.

    Represents a trading opportunity with side, confidence score,
    and explanation of the signal logic.
    """

    ticker: str
    side: str  # "yes" or "no"
    confidence: float  # 0.0 to 1.0
    reason: str
    features: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate signal after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")

        if self.side not in ["yes", "no"]:
            raise ValueError(f"Side must be 'yes' or 'no', got {self.side}")


class SignalGenerator:
    """Generates trading signals from weather and market data.

    Evaluates temperature and precipitation signals, calculates
    confidence scores, and combines multiple signals.
    """

    def __init__(self, min_confidence: float = 0.6) -> None:
        """Initialize signal generator.

        Args:
            min_confidence: Minimum confidence threshold for signals
        """
        self.min_confidence = min_confidence
        logger.info("signal_generator_initialized", min_confidence=min_confidence)

    def generate_temperature_signal(self, weather: dict[str, Any], market: Market) -> Signal | None:
        """Generate signal based on temperature forecast.

        Args:
            weather: Normalized weather data dictionary
            market: Market to evaluate

        Returns:
            Signal if opportunity detected, None otherwise

        Example:
            >>> generator = SignalGenerator()
            >>> signal = generator.generate_temperature_signal(weather, market)
        """
        if "temperature" not in weather or market.strike_price is None:
            return None

        forecast_temp = weather["temperature"]
        strike = market.strike_price

        # Simple logic: if forecast significantly above/below strike
        temp_diff = forecast_temp - strike

        # Calculate confidence based on temperature difference
        # Larger difference = higher confidence
        confidence = min(abs(temp_diff) / 10.0, 1.0)

        if confidence < self.min_confidence:
            return None

        # Determine side
        if temp_diff > 0:
            side = "yes"  # Forecast above strike
            reason = f"Forecast {forecast_temp}°F above strike {strike}°F"
        else:
            side = "no"  # Forecast below strike
            reason = f"Forecast {forecast_temp}°F below strike {strike}°F"

        signal = Signal(
            ticker=market.ticker,
            side=side,
            confidence=confidence,
            reason=reason,
            features={
                "forecast_temp": forecast_temp,
                "strike_price": strike,
                "temp_diff": temp_diff,
            },
        )

        logger.info(
            "temperature_signal_generated",
            ticker=market.ticker,
            side=side,
            confidence=confidence,
        )

        return signal

    def generate_precipitation_signal(
        self, weather: dict[str, Any], market: Market
    ) -> Signal | None:
        """Generate signal based on precipitation forecast.

        Args:
            weather: Normalized weather data dictionary
            market: Market to evaluate

        Returns:
            Signal if opportunity detected, None otherwise
        """
        if "precipitation_probability" not in weather:
            return None

        precip_prob = weather["precipitation_probability"]

        # Only generate signal if precipitation probability is significant
        if precip_prob < 0.3:
            return None

        # High precipitation probability suggests cooler temperatures
        # This is a simplified heuristic
        confidence = min(precip_prob, 0.8)

        if confidence < self.min_confidence:
            return None

        signal = Signal(
            ticker=market.ticker,
            side="no",  # Precipitation tends to lower high temps
            confidence=confidence,
            reason=f"High precipitation probability ({precip_prob:.0%})",
            features={"precipitation_probability": precip_prob},
        )

        logger.info(
            "precipitation_signal_generated",
            ticker=market.ticker,
            confidence=confidence,
        )

        return signal

    def calculate_confidence_score(self, weather: dict[str, Any], market: Market) -> float:
        """Calculate overall confidence score for a market.

        Args:
            weather: Normalized weather data dictionary
            market: Market to evaluate

        Returns:
            Confidence score from 0.0 to 1.0
        """
        score = 0.0

        # Market quality component (0-0.4)
        if market.spread_cents is not None and market.spread_cents <= 3:
            score += 0.2

        total_liquidity = market.volume + market.open_interest
        if total_liquidity >= 1000:
            score += 0.2

        # Weather data quality component (0-0.3)
        if "temperature" in weather and weather["temperature"] is not None:
            score += 0.15

        if "precipitation_probability" in weather:
            score += 0.15

        # Market status component (0-0.3)
        if market.status == "open":
            score += 0.3

        logger.debug(
            "confidence_score_calculated",
            ticker=market.ticker,
            score=score,
        )

        return min(score, 1.0)

    def combine_signals(self, signals: list[Signal]) -> Signal | None:
        """Combine multiple signals into a single consensus signal.

        Args:
            signals: List of signals to combine

        Returns:
            Combined signal, or None if no consensus

        Note:
            Uses weighted average of confidence scores.
            Requires majority agreement on side.
        """
        if not signals:
            return None

        # Count votes for each side
        yes_votes = sum(1 for s in signals if s.side == "yes")
        no_votes = sum(1 for s in signals if s.side == "no")

        # Require majority
        if yes_votes == no_votes:
            logger.debug("signal_combination_no_consensus", yes_votes=yes_votes, no_votes=no_votes)
            return None

        # Determine consensus side
        consensus_side = "yes" if yes_votes > no_votes else "no"

        # Calculate weighted average confidence
        consensus_signals = [s for s in signals if s.side == consensus_side]
        avg_confidence = sum(s.confidence for s in consensus_signals) / len(consensus_signals)

        # Combine reasons
        reasons = [s.reason for s in consensus_signals]
        combined_reason = "; ".join(reasons)

        # Combine features
        combined_features = {}
        for signal in consensus_signals:
            if signal.features:
                combined_features.update(signal.features)

        combined = Signal(
            ticker=signals[0].ticker,
            side=consensus_side,
            confidence=avg_confidence,
            reason=combined_reason,
            features=combined_features,
        )

        logger.info(
            "signals_combined",
            ticker=combined.ticker,
            side=consensus_side,
            confidence=avg_confidence,
            num_signals=len(signals),
        )

        return combined
