"""Unit tests for strategy interface."""

import pytest

from src.trader.strategy import ReasonCode, Signal, Strategy


class TestReasonCode:
    """Test suite for ReasonCode enum."""

    def test_reason_code_values(self) -> None:
        """Test reason codes have correct values."""
        assert ReasonCode.STRONG_EDGE.value == "strong_edge"
        assert ReasonCode.INSUFFICIENT_EDGE.value == "insufficient_edge"
        assert ReasonCode.SPREAD_OK.value == "spread_ok"


class TestSignal:
    """Test suite for Signal dataclass."""

    def test_signal_creation(self) -> None:
        """Test creating a Signal instance."""
        signal = Signal(
            ticker="HIGHNYC-25JAN26",
            p_yes=0.65,
            uncertainty=0.10,
            edge=5.0,
            decision="BUY",
            side="yes",
            max_price=60.0,
            reasons=[ReasonCode.STRONG_EDGE, ReasonCode.SPREAD_OK],
        )

        assert signal.ticker == "HIGHNYC-25JAN26"
        assert signal.p_yes == 0.65
        assert signal.uncertainty == 0.10
        assert signal.edge == 5.0
        assert signal.decision == "BUY"
        assert signal.side == "yes"

    def test_signal_validates_p_yes_range(self) -> None:
        """Test Signal validates p_yes is between 0 and 1."""
        with pytest.raises(ValueError, match="p_yes must be between 0 and 1"):
            Signal(
                ticker="TEST-01",
                p_yes=1.5,
                uncertainty=0.1,
                edge=5.0,
                decision="HOLD",
            )

    def test_signal_validates_uncertainty_non_negative(self) -> None:
        """Test Signal validates uncertainty is non-negative."""
        with pytest.raises(ValueError, match="uncertainty must be non-negative"):
            Signal(
                ticker="TEST-01",
                p_yes=0.5,
                uncertainty=-0.1,
                edge=5.0,
                decision="HOLD",
            )

    def test_signal_validates_decision(self) -> None:
        """Test Signal validates decision is BUY/SELL/HOLD."""
        with pytest.raises(ValueError, match="decision must be BUY/SELL/HOLD"):
            Signal(
                ticker="TEST-01",
                p_yes=0.5,
                uncertainty=0.1,
                edge=5.0,
                decision="INVALID",
            )

    def test_signal_requires_side_for_buy_decision(self) -> None:
        """Test Signal requires side when decision is BUY."""
        with pytest.raises(ValueError, match="side required when decision is BUY"):
            Signal(
                ticker="TEST-01",
                p_yes=0.65,
                uncertainty=0.1,
                edge=5.0,
                decision="BUY",
                side=None,
            )

    def test_signal_hold_decision_no_side_required(self) -> None:
        """Test Signal allows None side for HOLD decision."""
        signal = Signal(
            ticker="TEST-01",
            p_yes=0.5,
            uncertainty=0.1,
            edge=0.0,
            decision="HOLD",
        )

        assert signal.side is None


class TestStrategy:
    """Test suite for Strategy base class."""

    def test_strategy_initialization(self) -> None:
        """Test Strategy initializes with name and min_edge."""
        strategy = Strategy(name="test_strategy", min_edge=0.01)

        assert strategy.name == "test_strategy"
        assert strategy.min_edge == 0.01

    def test_strategy_evaluate_not_implemented(self) -> None:
        """Test Strategy.evaluate() raises NotImplementedError."""
        from src.shared.api.response_models import Market
        
        strategy = Strategy(name="test")
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            status="open",
        )

        with pytest.raises(NotImplementedError):
            strategy.evaluate(weather={}, market=market)

    def test_calculate_threshold_probability_above_threshold(self) -> None:
        """Test probability calculation when forecast above threshold."""
        strategy = Strategy(name="test")

        # Forecast 35°F, threshold 32°F, std_dev 3°F
        # z-score = (35-32)/3 = 1.0
        # P(X >= 32) = 1 - CDF(1.0) ≈ 0.1587
        p = strategy.calculate_threshold_probability(
            forecast_value=35.0,
            threshold=32.0,
            std_dev=3.0,
        )

        assert 0.15 <= p <= 0.17  # Approximately 15.87%

    def test_calculate_threshold_probability_at_threshold(self) -> None:
        """Test probability calculation when forecast equals threshold."""
        strategy = Strategy(name="test")

        # Forecast = threshold, z-score = 0
        # P(X >= threshold) = 0.5
        p = strategy.calculate_threshold_probability(
            forecast_value=32.0,
            threshold=32.0,
            std_dev=3.0,
        )

        assert 0.49 <= p <= 0.51  # Approximately 50%

    def test_calculate_threshold_probability_below_threshold(self) -> None:
        """Test probability calculation when forecast below threshold."""
        strategy = Strategy(name="test")

        # Forecast 29°F, threshold 32°F, std_dev 3°F
        # z-score = (29-32)/3 = -1.0
        # P(X >= 32) = 1 - CDF(-1.0) ≈ 0.8413
        p = strategy.calculate_threshold_probability(
            forecast_value=29.0,
            threshold=32.0,
            std_dev=3.0,
        )

        assert 0.83 <= p <= 0.85  # Approximately 84.13%

    def test_calculate_threshold_probability_zero_std_dev(self) -> None:
        """Test probability calculation with zero standard deviation."""
        strategy = Strategy(name="test")

        # No uncertainty: deterministic
        p_above = strategy.calculate_threshold_probability(
            forecast_value=35.0,
            threshold=32.0,
            std_dev=0.0,
        )
        assert p_above == 0.0  # Forecast > threshold, so P(X >= threshold) = 0

        p_below = strategy.calculate_threshold_probability(
            forecast_value=30.0,
            threshold=32.0,
            std_dev=0.0,
        )
        assert p_below == 1.0  # Forecast < threshold, so P(X >= threshold) = 1

    def test_calculate_edge_positive(self) -> None:
        """Test edge calculation with positive edge."""
        strategy = Strategy(name="test")

        # p_yes=0.60, market=50¢, cost=1¢
        # Expected value = 0.60 * 100 = 60¢
        # Edge = 60 - 50 - 1 = 9¢
        edge = strategy.calculate_edge(
            p_yes=0.60,
            market_price=50.0,
            transaction_cost=1.0,
        )

        assert edge == 9.0

    def test_calculate_edge_negative(self) -> None:
        """Test edge calculation with negative edge."""
        strategy = Strategy(name="test")

        # p_yes=0.40, market=50¢, cost=1¢
        # Expected value = 0.40 * 100 = 40¢
        # Edge = 40 - 50 - 1 = -11¢
        edge = strategy.calculate_edge(
            p_yes=0.40,
            market_price=50.0,
            transaction_cost=1.0,
        )

        assert edge == -11.0

    def test_calculate_edge_zero_cost(self) -> None:
        """Test edge calculation with zero transaction cost."""
        strategy = Strategy(name="test")

        edge = strategy.calculate_edge(
            p_yes=0.55,
            market_price=50.0,
            transaction_cost=0.0,
        )

        assert edge == 5.0  # 55 - 50
