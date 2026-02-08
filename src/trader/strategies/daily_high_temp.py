"""Daily high temperature strategy.

Generates trading signals for daily high temperature markets using
forecast data and historical variance.
"""

from typing import Any

from src.shared.api.response_models import Market
from src.shared.config.logging import get_logger
from src.trader.strategy import ReasonCode, Signal, Strategy

logger = get_logger(__name__)


class DailyHighTempStrategy(Strategy):
    """Strategy for daily high temperature markets.

    Uses NWS forecast high temperature and historical variance to
    calculate probability of exceeding threshold. Returns HOLD if
    uncertainty exceeds configured maximum.
    """

    def __init__(
        self,
        name: str = "daily_high_temp",
        min_edge: float = 0.03,
        max_uncertainty: float = 0.30,
        default_std_dev: float = 3.0,
        transaction_cost: float = 1.5,
    ) -> None:
        """Initialize daily high temperature strategy.

        Live trading settings tuned for capital preservation:
        - 3% min_edge aligned with gate threshold for consistent filtering
        - 30% max_uncertainty (matches default 3.0°F std_dev normalization)
        - 1.5¢ transaction cost covers exchange fee + taker spread

        Args:
            name: Strategy name
            min_edge: Minimum edge required to trade (3% for live)
            max_uncertainty: Maximum uncertainty allowed (30% for live)
            default_std_dev: Default forecast std dev in °F (3.0°F standard)
            transaction_cost: Estimated transaction cost in cents
        """
        super().__init__(name=name, min_edge=min_edge)
        self.max_uncertainty = max_uncertainty
        self.default_std_dev = default_std_dev
        self.transaction_cost = transaction_cost

        logger.info(
            "daily_high_temp_strategy_initialized",
            max_uncertainty=max_uncertainty,
            default_std_dev=default_std_dev,
        )

    def evaluate(
        self,
        weather: dict[str, Any],
        market: Market,
    ) -> Signal:
        """Evaluate daily high temperature market.

        Args:
            weather: Normalized weather data with forecast high temp
            market: Market to evaluate (must have strike_price)

        Returns:
            Signal with probability estimate and decision
        """
        reasons: list[ReasonCode] = []

        # Validate inputs
        if "temperature" not in weather or weather["temperature"] is None:
            logger.warning("missing_forecast_temperature", ticker=market.ticker)
            return Signal(
                ticker=market.ticker,
                p_yes=0.5,
                uncertainty=1.0,
                edge=0.0,
                decision="HOLD",
                reasons=[ReasonCode.MISSING_DATA],
                features={
                    "forecast_high": None,
                    "threshold": market.strike_price,
                    "std_dev": self.default_std_dev,
                    "market_price": None,
                },
            )

        if market.strike_price is None:
            logger.warning("missing_strike_price", ticker=market.ticker)
            return Signal(
                ticker=market.ticker,
                p_yes=0.5,
                uncertainty=1.0,
                edge=0.0,
                decision="HOLD",
                reasons=[ReasonCode.MISSING_DATA],
                features={
                    "forecast_high": weather.get("temperature"),
                    "threshold": None,
                    "std_dev": self.default_std_dev,
                    "market_price": None,
                },
            )

        forecast_high = weather["temperature"]
        threshold = market.strike_price

        # Get standard deviation (use historical if available, else default)
        std_dev = weather.get("forecast_std_dev", self.default_std_dev)

        # Calculate probability of high >= threshold
        # P(high >= threshold) where high ~ N(forecast_high, std_dev^2)
        # Using error function approximation for normal CDF
        import math
        
        # Z-score: how many std devs is threshold above forecast
        z_score = (threshold - forecast_high) / std_dev
        
        # Approximate normal CDF using error function
        # CDF(z) = 0.5 * (1 + erf(z / sqrt(2)))
        # P(high >= threshold) = 1 - CDF(z_score) = 0.5 * (1 - erf(z_score / sqrt(2)))
        p_yes = 0.5 * (1.0 - math.erf(z_score / math.sqrt(2.0)))

        # Calculate uncertainty (normalized std dev)
        uncertainty = min(std_dev / 10.0, 1.0)  # Normalize to 0-1

        # Get market price (use mid price if available)
        market_price = market.mid_price

        # Collect all reason codes before making decision
        # Check if market pricing is missing
        if market.yes_bid is None and market.yes_ask is None:
            logger.warning("missing_market_pricing", ticker=market.ticker)
            if ReasonCode.MISSING_DATA not in reasons:
                reasons.append(ReasonCode.MISSING_DATA)

        # Check if market price unavailable
        if market_price is None:
            logger.warning("missing_market_price", ticker=market.ticker)
            if ReasonCode.MISSING_DATA not in reasons:
                reasons.append(ReasonCode.MISSING_DATA)

        # Check if uncertainty too high
        if uncertainty > self.max_uncertainty:
            logger.info(
                "high_uncertainty",
                ticker=market.ticker,
                uncertainty=uncertainty,
                max_uncertainty=self.max_uncertainty,
            )
            reasons.append(ReasonCode.HIGH_UNCERTAINTY)

        # Calculate edge for the side we would trade
        # Edge depends on whether we're buying YES or NO
        edge = 0.0
        if market_price is not None:
            if p_yes > 0.5:
                # Would buy YES: edge = fair_value - market_price
                # fair_value for YES = p_yes * 100
                edge = p_yes * 100 - market_price - self.transaction_cost
            else:
                # Would buy NO: edge = fair_value_no - market_no_price
                # fair_value for NO = (1 - p_yes) * 100
                # market_no_price = 100 - market_yes_price
                market_no_price = 100 - market_price
                edge = (1 - p_yes) * 100 - market_no_price - self.transaction_cost

            # Check if edge insufficient (edge is in cents, min_edge is fraction)
            if edge < self.min_edge * 100:
                if ReasonCode.INSUFFICIENT_EDGE not in reasons:
                    reasons.append(ReasonCode.INSUFFICIENT_EDGE)

        # Make decision: if any blocking reasons exist, return HOLD
        if reasons:
            logger.info(
                "hold_decision",
                ticker=market.ticker,
                reasons=[r.value for r in reasons],
            )
            return Signal(
                ticker=market.ticker,
                p_yes=p_yes,
                uncertainty=uncertainty,
                edge=edge,
                decision="HOLD",
                side=None,
                max_price=None,
                reasons=reasons,
                features={
                    "forecast_high": forecast_high,
                    "threshold": threshold,
                    "std_dev": std_dev,
                    "market_price": market_price,
                },
            )

        # No blocking reasons: make BUY decision based on edge
        # p_yes = probability that high temp >= threshold
        # If p_yes > 0.5: likely to exceed → buy YES
        # If p_yes < 0.5: unlikely to exceed → buy NO
        if p_yes > 0.5:
            # Forecast above threshold - buy YES
            decision = "BUY"
            side = "yes"
            max_price = p_yes * 100 - self.transaction_cost
        else:
            # Forecast below threshold - buy NO
            decision = "BUY"
            side = "no"
            max_price = (1 - p_yes) * 100 - self.transaction_cost

        buy_reasons = [ReasonCode.STRONG_EDGE, ReasonCode.SPREAD_OK]

        signal = Signal(
            ticker=market.ticker,
            p_yes=p_yes,
            uncertainty=uncertainty,
            edge=edge,
            decision=decision,
            side=side,
            max_price=max_price,
            reasons=buy_reasons,
            features={
                "forecast_high": forecast_high,
                "threshold": threshold,
                "std_dev": std_dev,
                "market_price": market_price,
            },
        )

        logger.info(
            "signal_generated",
            ticker=market.ticker,
            p_yes=p_yes,
            edge=edge,
            decision=decision,
        )

        return signal
