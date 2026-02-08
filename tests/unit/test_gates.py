"""Unit tests for execution gate checks."""

import pytest

from src.shared.api.response_models import Market
from src.trader.gates import check_all_gates, check_edge, check_liquidity, check_spread
from src.trader.strategy import Signal


class TestCheckSpread:
    """Test suite for check_spread gate."""

    def test_check_spread_passes_tight_spread(self) -> None:
        """Test spread check passes with tight spread."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=48,  # 3 cent spread
            status="open",
        )

        result = check_spread(market, max_spread_cents=3)

        assert result is True

    def test_check_spread_fails_wide_spread(self) -> None:
        """Test spread check fails with wide spread."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=40,
            yes_ask=50,  # 10 cent spread
            status="open",
        )

        result = check_spread(market, max_spread_cents=3)

        assert result is False

    def test_check_spread_fails_no_pricing(self) -> None:
        """Test spread check fails when no pricing available."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            status="open",
            # No bid/ask prices
        )

        result = check_spread(market, max_spread_cents=3)

        assert result is False

    def test_check_spread_custom_max(self) -> None:
        """Test spread check with custom maximum."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=50,  # 5 cent spread
            status="open",
        )

        # Should fail with max=3
        assert check_spread(market, max_spread_cents=3) is False
        
        # Should pass with max=5
        assert check_spread(market, max_spread_cents=5) is True


class TestCheckLiquidity:
    """Test suite for check_liquidity gate."""

    def test_check_liquidity_passes_sufficient(self) -> None:
        """Test liquidity check passes with sufficient liquidity."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            volume=1000,
            open_interest=5000,  # Total 6000
            status="open",
        )

        # Want to trade 100, need 5x = 500
        result = check_liquidity(market, quantity=100, min_liquidity_multiple=5.0)

        assert result is True

    def test_check_liquidity_fails_insufficient(self) -> None:
        """Test liquidity check fails with insufficient liquidity."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            volume=100,
            open_interest=200,  # Total 300
            status="open",
        )

        # Want to trade 100, need 5x = 500
        result = check_liquidity(market, quantity=100, min_liquidity_multiple=5.0)

        assert result is False

    def test_check_liquidity_custom_multiple(self) -> None:
        """Test liquidity check with custom multiple."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            volume=500,
            open_interest=500,  # Total 1000
            status="open",
        )

        # Should pass with 10x multiple (need 1000)
        assert check_liquidity(market, quantity=100, min_liquidity_multiple=10.0) is True
        
        # Should fail with 20x multiple (need 2000)
        assert check_liquidity(market, quantity=100, min_liquidity_multiple=20.0) is False


class TestCheckEdge:
    """Test suite for check_edge gate."""

    def test_check_edge_passes_sufficient(self) -> None:
        """Test edge check passes with sufficient edge."""
        signal = Signal(
            ticker="TEST-01",
            p_yes=0.65,
            uncertainty=0.10,
            edge=5.0,  # 5 cents edge
            decision="BUY",
            side="yes",
        )

        result = check_edge(signal, min_edge_cents=0.5)

        assert result is True

    def test_check_edge_fails_insufficient(self) -> None:
        """Test edge check fails with insufficient edge."""
        signal = Signal(
            ticker="TEST-01",
            p_yes=0.51,
            uncertainty=0.10,
            edge=0.3,  # Only 0.3 cents edge
            decision="BUY",
            side="yes",
        )

        result = check_edge(signal, min_edge_cents=0.5)

        assert result is False

    def test_check_edge_negative_edge(self) -> None:
        """Test edge check fails with negative edge."""
        signal = Signal(
            ticker="TEST-01",
            p_yes=0.45,
            uncertainty=0.10,
            edge=-2.0,  # Negative edge
            decision="HOLD",
        )

        result = check_edge(signal, min_edge_cents=0.5)

        assert result is False


class TestCheckAllGates:
    """Test suite for check_all_gates function."""

    @pytest.fixture
    def good_signal(self) -> Signal:
        """Create signal with good edge."""
        return Signal(
            ticker="TEST-01",
            p_yes=0.65,
            uncertainty=0.10,
            edge=5.0,
            decision="BUY",
            side="yes",
        )

    @pytest.fixture
    def good_market(self) -> Market:
        """Create market with good conditions."""
        return Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=48,  # 3 cent spread
            volume=1000,
            open_interest=5000,
            status="open",
        )

    def test_check_all_gates_all_pass(
        self, good_signal: Signal, good_market: Market
    ) -> None:
        """Test all gates pass with good conditions."""
        passed, reasons = check_all_gates(
            signal=good_signal,
            market=good_market,
            quantity=100,
        )

        assert passed is True
        assert len(reasons) == 0

    def test_check_all_gates_spread_fails(
        self, good_signal: Signal
    ) -> None:
        """Test all gates when spread check fails."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=40,
            yes_ask=50,  # 10 cent spread
            volume=1000,
            open_interest=5000,
            status="open",
        )

        passed, reasons = check_all_gates(
            signal=good_signal,
            market=market,
            quantity=100,
        )

        assert passed is False
        assert "spread_too_wide" in reasons

    def test_check_all_gates_liquidity_fails(
        self, good_signal: Signal
    ) -> None:
        """Test all gates when liquidity check fails."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=48,
            volume=50,
            open_interest=100,  # Total 150, need 300 (3.0x * 100)
            status="open",
        )

        passed, reasons = check_all_gates(
            signal=good_signal,
            market=market,
            quantity=100,
        )

        assert passed is False
        assert "insufficient_liquidity" in reasons

    def test_check_all_gates_edge_fails(self, good_market: Market) -> None:
        """Test all gates when edge check fails."""
        signal = Signal(
            ticker="TEST-01",
            p_yes=0.51,
            uncertainty=0.10,
            edge=0.3,  # Insufficient edge
            decision="BUY",
            side="yes",
        )

        passed, reasons = check_all_gates(
            signal=signal,
            market=good_market,
            quantity=100,
        )

        assert passed is False
        assert "insufficient_edge" in reasons

    def test_check_all_gates_multiple_failures(self) -> None:
        """Test all gates with multiple failures."""
        signal = Signal(
            ticker="TEST-01",
            p_yes=0.51,
            uncertainty=0.10,
            edge=0.3,  # Insufficient edge
            decision="BUY",
            side="yes",
        )
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=40,
            yes_ask=50,  # Wide spread
            volume=50,
            open_interest=100,  # Low liquidity
            status="open",
        )

        passed, reasons = check_all_gates(
            signal=signal,
            market=market,
            quantity=100,
        )

        assert passed is False
        assert len(reasons) == 3  # All three gates should fail
        assert "spread_too_wide" in reasons
        assert "insufficient_liquidity" in reasons
        assert "insufficient_edge" in reasons
