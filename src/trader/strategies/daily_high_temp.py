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
        min_edge: float = 0.005,
        max_uncertainty: float = 0.20,
        default_std_dev: float = 3.0,
        transaction_cost: float = 1.0,
    ) -> None:
        """Initialize daily high temperature strategy.

        Args:
            name: Strategy name
            min_edge: Minimum edge required to trade (default 0.5%)
            max_uncertainty: Maximum uncertainty allowed (default 20%)
            default_std_dev: Default forecast std dev in °F (default 3°F)
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
                    "forecast_value": None,
                    "strike_price": market.strike_price,
                    "std_dev_used": self.default_std_dev,
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
                    "forecast_value": weather.get("temperature"),
                    "strike_price": None,
                    "std_dev_used": self.default_std_dev,
                    "market_price": None,
                },
            )

        forecast_high = weather["temperature"]
        threshold = market.strike_price

        # Get standard deviation (use historical if available, else default)
        std_dev = weather.get("forecast_std_dev", self.default_std_dev)

        # Check if market pricing is missing
        if market.yes_bid is None and market.yes_ask is None:
            logger.warning("missing_market_pricing", ticker=market.ticker)
            reasons.append(ReasonCode.MISSING_DATA)

        # Calculate probability of high >= threshold
        p_yes = self.calculate_threshold_probability(
            forecast_value=forecast_high,
            threshold=threshold,
            std_dev=std_dev,
        )

        # Calculate uncertainty (normalized std dev)
        uncertainty = min(std_dev / 10.0, 1.0)  # Normalize to 0-1

        # Check if uncertainty too high
        if uncertainty > self.max_uncertainty:
            logger.info(
                "high_uncertainty_hold",
                ticker=market.ticker,
                uncertainty=uncertainty,
                max_uncertainty=self.max_uncertainty,
            )
            return Signal(
                ticker=market.ticker,
                p_yes=p_yes,
                uncertainty=uncertainty,
                edge=0.0,
                decision="HOLD",
                reasons=[ReasonCode.HIGH_UNCERTAINTY],
                features={
                    "forecast_value": forecast_high,
                    "strike_price": threshold,
                    "std_dev_used": std_dev,
                    "market_price": None,
                },
            )

        # Get market price (use mid price if available)
        market_price = market.mid_price
        if market_price is None:
            logger.warning("missing_market_price", ticker=market.ticker)
            return Signal(
                ticker=market.ticker,
                p_yes=p_yes,
                uncertainty=uncertainty,
                edge=0.0,
                decision="HOLD",
                reasons=[ReasonCode.MISSING_DATA],
                features={
                    "forecast_value": forecast_high,
                    "strike_price": threshold,
                    "std_dev_used": std_dev,
                    "market_price": None,
                },
            )

        # Calculate edge
        edge = self.calculate_edge(
            p_yes=p_yes,
            market_price=market_price,
            transaction_cost=self.transaction_cost,
        )

        # Check if edge is insufficient
        if edge < self.min_edge * 100:  # Convert min_edge to cents
            reasons.append(ReasonCode.INSUFFICIENT_EDGE)

        # Make decision
        if edge >= self.min_edge * 100:  # Convert min_edge to cents
            # Positive edge: buy YES if p_yes > 0.5, buy NO otherwise
            if p_yes > 0.5:
                decision = "BUY"
                side = "yes"
                max_price = p_yes * 100 - self.transaction_cost
            else:
                decision = "BUY"
                side = "no"
                max_price = (1 - p_yes) * 100 - self.transaction_cost

            reasons.extend([ReasonCode.STRONG_EDGE, ReasonCode.SPREAD_OK])
        else:
            decision = "HOLD"
            side = None
            max_price = None

        signal = Signal(
            ticker=market.ticker,
            p_yes=p_yes,
            uncertainty=uncertainty,
            edge=edge,
            decision=decision,
            side=side,
            max_price=max_price,
            reasons=reasons,
            features={
                "forecast_value": forecast_high,
                "strike_price": threshold,
                "std_dev_used": std_dev,
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
