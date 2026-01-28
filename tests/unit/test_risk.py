"""Unit tests for risk calculator and circuit breakers."""

import time

import pytest

from src.trader.risk import CircuitBreaker, RiskCalculator


class TestRiskCalculator:
    """Test suite for RiskCalculator."""

    @pytest.fixture
    def calculator(self) -> RiskCalculator:
        """Create risk calculator instance."""
        return RiskCalculator(
            max_city_exposure_pct=0.03,
            max_cluster_exposure_pct=0.05,
            max_trade_risk_pct=0.02,
            bankroll=5000.0,
        )

    def test_calculator_initialization(self, calculator: RiskCalculator) -> None:
        """Test RiskCalculator initializes with correct limits."""
        assert calculator.bankroll == 5000.0
        assert calculator.max_city_exposure == 150.0  # 3% of 5000
        assert calculator.max_cluster_exposure == 250.0  # 5% of 5000
        assert calculator.max_trade_risk == 100.0  # 2% of 5000

    def test_calculate_open_risk_single_position(self, calculator: RiskCalculator) -> None:
        """Test calculating open risk with single position."""
        positions = [{"ticker": "TEST-01", "quantity": 100, "entry_price": 45.0}]

        risk = calculator.calculate_open_risk(positions)

        assert risk == 45.0  # 100 * 45 / 100

    def test_calculate_open_risk_multiple_positions(self, calculator: RiskCalculator) -> None:
        """Test calculating open risk with multiple positions."""
        positions = [
            {"ticker": "TEST-01", "quantity": 100, "entry_price": 45.0},
            {"ticker": "TEST-02", "quantity": 50, "entry_price": 60.0},
        ]

        risk = calculator.calculate_open_risk(positions)

        assert risk == 75.0  # (100 * 45 + 50 * 60) / 100

    def test_calculate_open_risk_empty_positions(self, calculator: RiskCalculator) -> None:
        """Test calculating open risk with no positions."""
        risk = calculator.calculate_open_risk([])

        assert risk == 0.0

    def test_check_city_exposure_within_limit(self, calculator: RiskCalculator) -> None:
        """Test city exposure check passes when within limit."""
        existing_positions = [{"city_code": "NYC", "quantity": 100, "entry_price": 45.0}]

        # Current exposure: $45, new trade: $50, total: $95 < $150 limit
        allowed = calculator.check_city_exposure("NYC", 50.0, existing_positions)

        assert allowed is True

    def test_check_city_exposure_exceeds_limit(self, calculator: RiskCalculator) -> None:
        """Test city exposure check fails when exceeding limit."""
        existing_positions = [{"city_code": "NYC", "quantity": 200, "entry_price": 50.0}]

        # Current exposure: $100, new trade: $100, total: $200 > $150 limit
        allowed = calculator.check_city_exposure("NYC", 100.0, existing_positions)

        assert allowed is False

    def test_check_city_exposure_different_cities(self, calculator: RiskCalculator) -> None:
        """Test city exposure only counts positions for same city."""
        existing_positions = [
            {"city_code": "NYC", "quantity": 100, "entry_price": 50.0},
            {"city_code": "CHI", "quantity": 100, "entry_price": 50.0},
        ]

        # NYC exposure: $50, new trade: $50, total: $100 < $150 limit
        allowed = calculator.check_city_exposure("NYC", 50.0, existing_positions)

        assert allowed is True

    def test_check_cluster_exposure_within_limit(self, calculator: RiskCalculator) -> None:
        """Test cluster exposure check passes when within limit."""
        existing_positions = [{"cluster": "NE", "quantity": 100, "entry_price": 50.0}]

        # Current exposure: $50, new trade: $100, total: $150 < $250 limit
        allowed = calculator.check_cluster_exposure("NE", 100.0, existing_positions)

        assert allowed is True

    def test_check_cluster_exposure_exceeds_limit(self, calculator: RiskCalculator) -> None:
        """Test cluster exposure check fails when exceeding limit."""
        existing_positions = [{"cluster": "NE", "quantity": 300, "entry_price": 50.0}]

        # Current exposure: $150, new trade: $150, total: $300 > $250 limit
        allowed = calculator.check_cluster_exposure("NE", 150.0, existing_positions)

        assert allowed is False

    def test_check_cluster_exposure_different_clusters(self, calculator: RiskCalculator) -> None:
        """Test cluster exposure only counts positions for same cluster."""
        existing_positions = [
            {"cluster": "NE", "quantity": 100, "entry_price": 50.0},
            {"cluster": "SE", "quantity": 100, "entry_price": 50.0},
        ]

        # NE exposure: $50, new trade: $100, total: $150 < $250 limit
        allowed = calculator.check_cluster_exposure("NE", 100.0, existing_positions)

        assert allowed is True

    def test_check_trade_size_within_limits(self, calculator: RiskCalculator) -> None:
        """Test trade size check passes when within limits."""
        allowed = calculator.check_trade_size(trade_risk=50.0, quantity=100)

        assert allowed is True

    def test_check_trade_size_exceeds_risk_limit(self, calculator: RiskCalculator) -> None:
        """Test trade size check fails when risk exceeds limit."""
        # Max trade risk is $100
        allowed = calculator.check_trade_size(trade_risk=150.0, quantity=100)

        assert allowed is False

    def test_check_trade_size_exceeds_quantity_limit(self, calculator: RiskCalculator) -> None:
        """Test trade size check fails when quantity exceeds limit."""
        # MAX_POSITION_SIZE is 1000
        allowed = calculator.check_trade_size(trade_risk=50.0, quantity=1500)

        assert allowed is False


class TestCircuitBreaker:
    """Test suite for CircuitBreaker."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker:
        """Create circuit breaker instance."""
        return CircuitBreaker(
            max_daily_loss=250.0,
            max_rejects_window=5,
            reject_window_minutes=15,
        )

    def test_breaker_initialization(self, breaker: CircuitBreaker) -> None:
        """Test CircuitBreaker initializes correctly."""
        assert breaker.max_daily_loss == 250.0
        assert breaker.max_rejects_window == 5
        assert breaker.reject_window_minutes == 15
        assert breaker.is_paused is False

    def test_track_daily_pnl_positive(self, breaker: CircuitBreaker) -> None:
        """Test tracking positive daily P&L."""
        pnl = breaker.track_daily_pnl(realized_pnl=100.0, unrealized_pnl=50.0)

        assert pnl == 150.0

    def test_track_daily_pnl_negative(self, breaker: CircuitBreaker) -> None:
        """Test tracking negative daily P&L."""
        pnl = breaker.track_daily_pnl(realized_pnl=-100.0, unrealized_pnl=-50.0)

        assert pnl == -150.0

    def test_track_daily_pnl_mixed(self, breaker: CircuitBreaker) -> None:
        """Test tracking mixed daily P&L."""
        pnl = breaker.track_daily_pnl(realized_pnl=100.0, unrealized_pnl=-50.0)

        assert pnl == 50.0

    def test_check_daily_loss_limit_within_limit(self, breaker: CircuitBreaker) -> None:
        """Test daily loss check passes when within limit."""
        allowed = breaker.check_daily_loss_limit(
            realized_pnl=-100.0,
            unrealized_pnl=-50.0,
        )

        # Total loss: -$150 < -$250 limit
        assert allowed is True
        assert breaker.is_paused is False

    def test_check_daily_loss_limit_exceeds_limit(self, breaker: CircuitBreaker) -> None:
        """Test daily loss check triggers pause when limit exceeded."""
        allowed = breaker.check_daily_loss_limit(
            realized_pnl=-200.0,
            unrealized_pnl=-100.0,
        )

        # Total loss: -$300 > -$250 limit
        assert allowed is False
        assert breaker.is_paused is True
        assert breaker.pause_reason is not None
        assert "Daily loss" in breaker.pause_reason

    def test_check_daily_loss_limit_pause_persists(self, breaker: CircuitBreaker) -> None:
        """Test pause state persists across multiple checks."""
        # First check triggers pause
        breaker.check_daily_loss_limit(realized_pnl=-300.0, unrealized_pnl=0.0)
        assert breaker.is_paused is True

        # Second check should still be paused
        allowed = breaker.check_daily_loss_limit(realized_pnl=-300.0, unrealized_pnl=0.0)
        assert allowed is False
        assert breaker.is_paused is True

    def test_track_order_rejects_single(self, breaker: CircuitBreaker) -> None:
        """Test tracking single order reject."""
        count = breaker.track_order_rejects(time.time())

        assert count == 1
        assert breaker.is_paused is False

    def test_track_order_rejects_threshold(self, breaker: CircuitBreaker) -> None:
        """Test reject threshold triggers pause."""
        current_time = time.time()

        # Add 5 rejects (threshold)
        for i in range(5):
            count = breaker.track_order_rejects(current_time + i)

        assert count == 5
        assert breaker.is_paused is True
        assert breaker.pause_reason is not None
        assert "order rejects" in breaker.pause_reason

    def test_track_order_rejects_sliding_window(self, breaker: CircuitBreaker) -> None:
        """Test reject tracking uses sliding window."""
        current_time = time.time()

        # Add old rejects (outside window)
        old_time = current_time - (20 * 60)  # 20 minutes ago
        for i in range(3):
            breaker.track_order_rejects(old_time + i)

        # Add recent rejects
        for i in range(2):
            count = breaker.track_order_rejects(current_time + i)

        # Should only count recent rejects (2), not old ones
        assert count == 2
        assert breaker.is_paused is False

    def test_reset_pause(self, breaker: CircuitBreaker) -> None:
        """Test resetting pause state."""
        # Trigger pause
        breaker.check_daily_loss_limit(realized_pnl=-300.0, unrealized_pnl=0.0)
        assert breaker.is_paused is True

        # Reset
        breaker.reset_pause()

        assert breaker.is_paused is False
        assert breaker.pause_reason is None

    def test_reset_pause_clears_reject_history(self, breaker: CircuitBreaker) -> None:
        """Test reset clears reject history."""
        # Add rejects
        for i in range(3):
            breaker.track_order_rejects(time.time() + i)

        # Reset
        breaker.reset_pause()

        # Reject history should be cleared
        count = breaker.track_order_rejects(time.time())
        assert count == 1  # Only the new reject
