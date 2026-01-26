"""Strategy interface for trading signal generation.

Defines base Strategy class and Signal output model with probability
calculations for temperature threshold markets.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import scipy.stats as stats

from src.shared.api.response_models import Market
from src.shared.config.logging import get_logger

logger = get_logger(__name__)


class ReasonCode(Enum):
    """Enumerated reason codes for trading decisions."""

    # Positive signals
    STRONG_EDGE = "strong_edge"
    FORECAST_EXTREME = "forecast_extreme"
    SOURCES_AGREE = "sources_agree"
    SPREAD_OK = "spread_ok"
    LIQUIDITY_OK = "liquidity_ok"
    
    # Negative signals
    INSUFFICIENT_EDGE = "insufficient_edge"
    HIGH_UNCERTAINTY = "high_uncertainty"
    WIDE_SPREAD = "wide_spread"
    LOW_LIQUIDITY = "low_liquidity"
    STALE_DATA = "stale_data"
    MISSING_DATA = "missing_data"
    
    # Neutral
    NO_OPPORTUNITY = "no_opportunity"


@dataclass
class Signal:
    """Trading signal output from strategy evaluation.
    
    Represents a trading opportunity with probability estimate,
    uncertainty, edge calculation, and decision.
    """

    ticker: str
    p_yes: float  # Probability of YES outcome (0.0 to 1.0)
    uncertainty: float  # Uncertainty/confidence interval width
    edge: float  # Expected edge in cents after costs
    decision: str  # "BUY", "SELL", or "HOLD"
    side: str | None = None  # "yes" or "no" if decision is BUY/SELL
    max_price: float | None = None  # Maximum price willing to pay (cents)
    reasons: list[ReasonCode] | None = None
    features: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate signal after initialization."""
        if not 0.0 <= self.p_yes <= 1.0:
            raise ValueError(f"p_yes must be between 0 and 1, got {self.p_yes}")
        
        if self.uncertainty < 0.0:
            raise ValueError(f"uncertainty must be non-negative, got {self.uncertainty}")
        
        if self.decision not in ["BUY", "SELL", "HOLD"]:
            raise ValueError(f"decision must be BUY/SELL/HOLD, got {self.decision}")
        
        if self.decision in ["BUY", "SELL"] and self.side is None:
            raise ValueError(f"side required when decision is {self.decision}")


class Strategy:
    """Base class for trading strategies.
    
    All strategies must implement evaluate() method that returns
    a Signal with probability estimate and trading decision.
    """

    def __init__(self, name: str, min_edge: float = 0.005) -> None:
        """Initialize strategy.
        
        Args:
            name: Strategy name for logging and tracking
            min_edge: Minimum edge required to trade (default 0.5%)
        """
        self.name = name
        self.min_edge = min_edge
        logger.info("strategy_initialized", name=name, min_edge=min_edge)

    def evaluate(
        self,
        weather: dict[str, Any],
        market: Market,
    ) -> Signal:
        """Evaluate trading opportunity and generate signal.
        
        Args:
            weather: Normalized weather data dictionary
            market: Market to evaluate
            
        Returns:
            Signal with probability estimate and decision
            
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement evaluate()")

    def calculate_threshold_probability(
        self,
        forecast_value: float,
        threshold: float,
        std_dev: float,
    ) -> float:
        """Calculate probability that value exceeds threshold.
        
        Uses normal distribution assumption.
        
        Args:
            forecast_value: Forecasted value (e.g., temperature)
            threshold: Threshold to exceed
            std_dev: Standard deviation of forecast error
            
        Returns:
            Probability from 0.0 to 1.0
            
        Example:
            >>> strategy = Strategy("test")
            >>> p = strategy.calculate_threshold_probability(
            ...     forecast_value=35.0,
            ...     threshold=32.0,
            ...     std_dev=3.0,
            ... )
            >>> # p ≈ 0.84 (1 std dev above threshold)
        """
        if std_dev <= 0:
            # Degenerate case: no uncertainty
            return 1.0 if forecast_value >= threshold else 0.0
        
        # Calculate z-score
        z_score = (forecast_value - threshold) / std_dev
        
        # Probability of exceeding threshold
        p_exceed = 1.0 - stats.norm.cdf(z_score)
        
        logger.debug(
            "threshold_probability_calculated",
            forecast=forecast_value,
            threshold=threshold,
            std_dev=std_dev,
            z_score=z_score,
            probability=p_exceed,
        )
        
        return p_exceed

    def calculate_edge(
        self,
        p_yes: float,
        market_price: float,
        transaction_cost: float = 0.0,
    ) -> float:
        """Calculate expected edge after costs.
        
        Args:
            p_yes: Estimated probability of YES outcome
            market_price: Current market price (0-100 cents)
            transaction_cost: Estimated transaction cost in cents
            
        Returns:
            Edge in cents (positive = favorable)
            
        Example:
            >>> strategy = Strategy("test")
            >>> edge = strategy.calculate_edge(
            ...     p_yes=0.60,
            ...     market_price=50.0,
            ...     transaction_cost=1.0,
            ... )
            >>> # edge = (0.60 * 100 - 50.0) - 1.0 = 9.0 cents
        """
        # Expected value = p_yes * 100 (payout if YES wins)
        expected_value = p_yes * 100.0
        
        # Edge = expected value - market price - costs
        edge = expected_value - market_price - transaction_cost
        
        logger.debug(
            "edge_calculated",
            p_yes=p_yes,
            market_price=market_price,
            transaction_cost=transaction_cost,
            edge=edge,
        )
        
        return edge
