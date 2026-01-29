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
        assert signal.p_yes > 0.5  # High temp likely to exceed threshold
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

        assert signal.p_yes < 0.5  # High temp unlikely to exceed threshold
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

    def test_evaluate_forecast_equals_strike_exactly(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation when forecast exactly equals strike price."""
        weather = {
            "temperature": 32.0,  # Exactly at strike
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, sample_market)

        # p_yes should be approximately 0.5 when forecast = strike
        assert 0.45 <= signal.p_yes <= 0.55
        assert signal.features is not None
        assert signal.features["forecast_high"] == 32.0
        assert signal.features["threshold"] == 32.0

    def test_evaluate_with_custom_std_dev_in_weather(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation uses custom std dev from weather data."""
        weather = {
            "temperature": 35.0,
            "forecast_std_dev": 5.0,  # Custom std dev
        }

        signal = strategy.evaluate(weather, sample_market)

        assert signal.features is not None
        assert signal.features["std_dev"] == 5.0  # Should use provided value

    def test_evaluate_with_zero_volume_market(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation with market that has zero volume."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=48,
            volume=0,  # Zero volume
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 35.0,
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, market)

        # Should still evaluate (volume doesn't block evaluation)
        assert signal.ticker == "TEST-01"
        assert signal.p_yes is not None

    def test_evaluate_with_zero_open_interest(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation with market that has zero open interest."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=48,
            volume=1000,
            open_interest=0,  # Zero open interest
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 35.0,
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, market)

        # Should still evaluate
        assert signal.ticker == "TEST-01"
        assert signal.p_yes is not None

    def test_evaluate_yes_price_at_zero(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation when yes price is at 0 cents."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=0,
            yes_ask=2,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 10.0,  # Very unlikely to exceed threshold
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, market)

        assert signal.p_yes is not None
        # Market price should be very low
        assert signal.features is not None
        assert signal.features["market_price"] is not None

    def test_evaluate_yes_price_at_100(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation when yes price is at 100 cents."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=98,
            yes_ask=100,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 60.0,  # Very likely to exceed threshold
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, market)

        assert signal.p_yes is not None
        # Market price should be very high
        assert signal.features is not None
        assert signal.features["market_price"] is not None

    def test_evaluate_no_price_at_boundaries(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation when no price is at boundaries."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=1,
            yes_ask=3,
            no_bid=97,
            no_ask=99,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 10.0,
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, market)

        assert signal.p_yes is not None
        assert signal.features is not None

    def test_evaluate_max_price_calculation_yes_side(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test max_price calculation for yes side."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=30,
            yes_ask=35,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 45.0,  # Well above threshold
            "forecast_std_dev": 2.0,  # Low uncertainty
        }

        signal = strategy.evaluate(weather, market)

        if signal.decision == "BUY" and signal.side == "yes":
            assert signal.max_price is not None
            # max_price should be p_yes * 100 - transaction_cost
            expected_max = signal.p_yes * 100 - strategy.transaction_cost
            assert abs(signal.max_price - expected_max) < 0.01

    def test_evaluate_max_price_calculation_no_side(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test max_price calculation for no side."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=65,
            yes_ask=70,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 20.0,  # Well below threshold
            "forecast_std_dev": 2.0,  # Low uncertainty
        }

        signal = strategy.evaluate(weather, market)

        if signal.decision == "BUY" and signal.side == "no":
            assert signal.max_price is not None
            # max_price should be (1 - p_yes) * 100 - transaction_cost
            expected_max = (1 - signal.p_yes) * 100 - strategy.transaction_cost
            assert abs(signal.max_price - expected_max) < 0.01

    def test_evaluate_only_yes_bid_available(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation when only yes_bid is available."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=None,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 35.0,
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, market)

        # Should still calculate mid_price from available data
        assert signal.ticker == "TEST-01"

    def test_evaluate_only_yes_ask_available(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test evaluation when only yes_ask is available."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=None,
            yes_ask=48,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 35.0,
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, market)

        assert signal.ticker == "TEST-01"

    def test_evaluate_very_high_std_dev(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation with very high standard deviation."""
        weather = {
            "temperature": 35.0,
            "forecast_std_dev": 15.0,  # Very high uncertainty
        }

        signal = strategy.evaluate(weather, sample_market)

        # Should trigger high uncertainty hold
        assert signal.decision == "HOLD"
        assert ReasonCode.HIGH_UNCERTAINTY in signal.reasons
        # Uncertainty should be capped at 1.0
        assert signal.uncertainty <= 1.0

    def test_evaluate_very_low_std_dev(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation with very low standard deviation."""
        weather = {
            "temperature": 42.0,
            "forecast_std_dev": 0.5,  # Very low uncertainty
        }

        signal = strategy.evaluate(weather, sample_market)

        # Low uncertainty should allow trading if other conditions met
        assert signal.uncertainty < 0.1
        assert signal.features is not None
        assert signal.features["std_dev"] == 0.5

    def test_evaluate_temperature_none_value(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test evaluation when temperature is explicitly None."""
        weather = {
            "temperature": None,
        }

        signal = strategy.evaluate(weather, sample_market)

        assert signal.decision == "HOLD"
        assert ReasonCode.MISSING_DATA in signal.reasons

    def test_evaluate_strong_edge_reason_code(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test that STRONG_EDGE reason code is included in BUY decisions."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=20,
            yes_ask=25,  # Low price
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 50.0,  # Very likely to exceed
            "forecast_std_dev": 2.0,
        }

        signal = strategy.evaluate(weather, market)

        if signal.decision == "BUY":
            assert ReasonCode.STRONG_EDGE in signal.reasons
            assert ReasonCode.SPREAD_OK in signal.reasons

    def test_evaluate_features_always_populated(
        self, strategy: DailyHighTempStrategy, sample_market: Market
    ) -> None:
        """Test that features dict is always populated."""
        weather = {
            "temperature": 35.0,
            "forecast_std_dev": 3.0,
        }

        signal = strategy.evaluate(weather, sample_market)

        assert signal.features is not None
        assert "forecast_high" in signal.features
        assert "threshold" in signal.features
        assert "std_dev" in signal.features
        assert "market_price" in signal.features

    def test_evaluate_buy_no_side_when_forecast_below_threshold(
        self, strategy: DailyHighTempStrategy
    ) -> None:
        """Test BUY NO decision when forecast well below threshold."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=60,
            yes_ask=65,  # Market pricing YES at 62.5 (mid)
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )
        weather = {
            "temperature": 15.0,  # Well below threshold (32°F)
            "forecast_std_dev": 2.0,  # Low uncertainty
        }

        signal = strategy.evaluate(weather, market)

        # When forecast (15°F) is well below threshold (32°F), p_yes should be very low
        assert signal.p_yes < 0.5, f"Expected p_yes < 0.5 when forecast below threshold, got {signal.p_yes}"
        # Should generate BUY signal for NO side (huge edge: fair NO ~100, market NO ~37.5)
        assert signal.decision == "BUY", f"Expected BUY but got {signal.decision}, reasons: {signal.reasons}"
        assert signal.side == "no"
        assert signal.max_price is not None
        # max_price should be (1 - p_yes) * 100 - transaction_cost
        expected_max = (1 - signal.p_yes) * 100 - strategy.transaction_cost
        assert abs(signal.max_price - expected_max) < 0.01
