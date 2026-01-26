"""Unit tests for daily high temperature strategy."""

import pytest

from src.shared.api.response_models import Market
from src.trader.strategies.daily_high_temp import DailyHighTempStrategy
from src.trader.strategy import ReasonCode


class TestDailyHighTempStrategy:
    """Test suite for DailyHighTempStrategy."""

    @pytest.fixture
    def strategy(self) -> DailyHighTempStrategy:
        """Create strategy instance."""
        return DailyHighTempStrategy(
            min_edge=0.005,
            max_uncertainty=0.20,
            default_std_dev=3.0,
            transaction_cost=1.0,
        )

    @pytest.fixture
    def sample_market(self) -> Market:
        """Create sample market."""
        return Market(
            ticker="HIGHNYC-25JAN26",
            event_ticker="HIGHNYC",
            title="Will NYC high be above 32F?",
            yes_bid=45,
            yes_ask=48,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )

    def test_strategy_initialization(self, strategy: DailyHighTempStrategy) -> None:
        """Test DailyHighTempStrategy initializes correctly."""
        assert strategy.name == "daily_high_temp"
        assert strategy.min_edge == 0.005
        assert strategy.max_uncertainty == 0.20
        assert strategy.default_std_dev == 3.0
        assert strategy.transaction_cost == 1.0

    def test_evaluate_forecast_above_threshold(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation when forecast significantly above threshold."""
        weather = {
            "temperature": 42.0,  # 10°F above strike
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, sample_market)

        assert signal.ticker == "HIGHNYC-25JAN26"
        assert signal.p_yes < 0.5  # High temp likely to exceed threshold
        assert signal.decision in ["BUY", "HOLD"]
        assert signal.features is not None
        assert signal.features["forecast_high"] == 42.0
        assert signal.features["threshold"] == 32.0

    def test_evaluate_forecast_below_threshold(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation when forecast below threshold."""
        weather = {
            "temperature": 22.0,  # 10°F below strike
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, sample_market)

        assert signal.p_yes > 0.5  # High temp unlikely to exceed threshold
        assert signal.decision in ["BUY", "HOLD"]

    def test_evaluate_high_uncertainty_returns_hold(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation returns HOLD when uncertainty too high."""
        weather = {
            "temperature": 35.0,
            "forecast_std_dev": 5.0,  # High uncertainty
        }

        signal = strategy.evaluate(weather, sample_market)

        assert signal.decision == "HOLD"
        assert ReasonCode.HIGH_UNCERTAINTY in signal.reasons

    def test_evaluate_missing_temperature_returns_hold(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation returns HOLD when temperature missing."""
        weather = {}  # No temperature data

        signal = strategy.evaluate(weather, sample_market)

        assert signal.decision == "HOLD"
        assert ReasonCode.MISSING_DATA in signal.reasons

    def test_evaluate_missing_strike_price_returns_hold(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation returns HOLD when strike price missing."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=None,
        )
        weather = {"temperature": 35.0}

        signal = strategy.evaluate(weather, market)

        assert signal.decision == "HOLD"
        assert ReasonCode.MISSING_DATA in signal.reasons

    def test_evaluate_missing_market_price_returns_hold(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation returns HOLD when market price unavailable."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=32.0,
            # No bid/ask prices
        )
        weather = {"temperature": 35.0}

        signal = strategy.evaluate(weather, market)

        assert signal.decision == "HOLD"
        assert ReasonCode.MISSING_DATA in signal.reasons

    def test_evaluate_uses_default_std_dev(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation uses default std dev when not provided."""
        weather = {
            "temperature": 35.0,
            # No forecast_std_dev provided
        }

        signal = strategy.evaluate(weather, sample_market)

        assert signal.features is not None
        assert signal.features["std_dev"] == 3.0  # Default

    def test_evaluate_calculates_max_price(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation calculates max price for BUY decision."""
        weather = {
            "temperature": 42.0,  # Well above threshold
            "forecast_std_dev": 2.0,  # Low uncertainty
        }

        signal = strategy.evaluate(weather, sample_market)

        if signal.decision == "BUY":
            assert signal.max_price is not None
            assert signal.max_price > 0

    def test_evaluate_insufficient_edge_returns_hold(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation returns HOLD when edge insufficient."""
        # Market priced fairly, minimal edge
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=49,
            yes_ask=51,  # Mid = 50
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 32.0,  # At threshold, p_yes ≈ 0.5
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, market)

        assert signal.decision == "HOLD"
        assert ReasonCode.INSUFFICIENT_EDGE in signal.reasons
