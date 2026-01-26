"""Unit tests for database models."""

from datetime import datetime, timezone

import pytest

from src.shared.models import Market, Order, Position, Trade, utcnow


class TestUtcnow:
    """Test suite for utcnow utility function."""

    def test_utcnow_returns_datetime(self) -> None:
        """Test that utcnow returns a datetime object."""
        now = utcnow()
        assert isinstance(now, datetime)

    def test_utcnow_has_timezone(self) -> None:
        """Test that utcnow returns timezone-aware datetime."""
        now = utcnow()
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc


class TestMarketModel:
    """Test suite for Market model."""

    def test_market_creation(self) -> None:
        """Test creating a Market instance."""
        market = Market(
            ticker="HIGHNYC-25JAN26",
            event_ticker="HIGHNYC",
            title="Will NYC high be above 32F on Jan 26?",
            city_code="NYC",
            market_type="high",
            yes_bid=45,
            yes_ask=48,
            no_bid=52,
            no_ask=55,
            volume=1000,
            open_interest=5000,
            status="active",
            last_updated=utcnow(),
        )

        assert market.ticker == "HIGHNYC-25JAN26"
        assert market.city_code == "NYC"
        assert market.market_type == "high"
        assert market.status == "active"

    def test_market_spread_bps(self) -> None:
        """Test spread calculation in basis points."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test Market",
            city_code="NYC",
            market_type="high",
            yes_bid=45,
            yes_ask=48,
            last_updated=utcnow(),
        )

        assert market.spread_bps == 300  # (48 - 45) * 100

    def test_market_spread_bps_none_when_no_pricing(self) -> None:
        """Test spread returns None when pricing unavailable."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test Market",
            city_code="NYC",
            market_type="high",
            last_updated=utcnow(),
        )

        assert market.spread_bps is None

    def test_market_mid_price(self) -> None:
        """Test mid price calculation."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test Market",
            city_code="NYC",
            market_type="high",
            yes_bid=45,
            yes_ask=48,
            last_updated=utcnow(),
        )

        assert market.mid_price == 46.5  # (45 + 48) / 2

    def test_market_mid_price_none_when_no_pricing(self) -> None:
        """Test mid price returns None when pricing unavailable."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test Market",
            city_code="NYC",
            market_type="high",
            last_updated=utcnow(),
        )

        assert market.mid_price is None

    def test_market_repr(self) -> None:
        """Test Market string representation."""
        market = Market(
            ticker="HIGHNYC-25JAN26",
            event_ticker="HIGHNYC",
            title="Test",
            city_code="NYC",
            market_type="high",
            status="active",
            last_updated=utcnow(),
        )

        repr_str = repr(market)
        assert "HIGHNYC-25JAN26" in repr_str
        assert "NYC" in repr_str
        assert "active" in repr_str


class TestPositionModel:
    """Test suite for Position model."""

    def test_position_creation(self) -> None:
        """Test creating a Position instance."""
        position = Position(
            market_id=1,
            ticker="HIGHNYC-25JAN26",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            status="open",
        )

        assert position.ticker == "HIGHNYC-25JAN26"
        assert position.side == "yes"
        assert position.quantity == 100
        assert position.status == "open"

    def test_position_update_pnl_yes_side(self) -> None:
        """Test P&L calculation for yes side position."""
        position = Position(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
        )

        position.update_pnl(50.0)

        assert position.current_price == 50.0
        assert position.unrealized_pnl == 500.0  # (50 - 45) * 100

    def test_position_update_pnl_no_side(self) -> None:
        """Test P&L calculation for no side position."""
        position = Position(
            market_id=1,
            ticker="TEST-01",
            side="no",
            quantity=100,
            entry_price=55.0,
            total_cost=5500.0,
        )

        position.update_pnl(50.0)

        assert position.current_price == 50.0
        assert position.unrealized_pnl == 500.0  # (55 - 50) * 100

    def test_position_close_position(self) -> None:
        """Test closing a position."""
        position = Position(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
        )

        closed_at = utcnow()
        position.close_position(settlement_price=60.0, closed_at=closed_at)

        assert position.status == "closed"
        assert position.settlement_price == 60.0
        assert position.closed_at == closed_at
        assert position.realized_pnl == 1500.0  # (60 - 45) * 100

    def test_position_repr(self) -> None:
        """Test Position string representation."""
        position = Position(
            market_id=1,
            ticker="HIGHNYC-25JAN26",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            status="open",
        )

        repr_str = repr(position)
        assert "HIGHNYC-25JAN26" in repr_str
        assert "yes" in repr_str
        assert "100" in repr_str
        assert "open" in repr_str


class TestOrderModel:
    """Test suite for Order model."""

    def test_order_creation(self) -> None:
        """Test creating an Order instance."""
        order = Order(
            market_id=1,
            ticker="HIGHNYC-25JAN26",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            limit_price=45.0,
            remaining_quantity=100,
            submitted_at=utcnow(),
        )

        assert order.ticker == "HIGHNYC-25JAN26"
        assert order.side == "yes"
        assert order.action == "buy"
        assert order.quantity == 100

    def test_order_is_filled_property(self) -> None:
        """Test is_filled property."""
        order = Order(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            filled_quantity=100,
            remaining_quantity=0,
            submitted_at=utcnow(),
        )

        assert order.is_filled is True

    def test_order_is_not_filled_property(self) -> None:
        """Test is_filled property when partially filled."""
        order = Order(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            filled_quantity=50,
            remaining_quantity=50,
            submitted_at=utcnow(),
        )

        assert order.is_filled is False

    def test_order_fill_rate(self) -> None:
        """Test fill rate calculation."""
        order = Order(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            filled_quantity=75,
            remaining_quantity=25,
            submitted_at=utcnow(),
        )

        assert order.fill_rate == 0.75

    def test_order_fill_rate_zero_quantity(self) -> None:
        """Test fill rate with zero quantity."""
        order = Order(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=0,
            filled_quantity=0,
            remaining_quantity=0,
            submitted_at=utcnow(),
        )

        assert order.fill_rate == 0.0

    def test_order_update_fill_partial(self) -> None:
        """Test updating order with partial fill."""
        order = Order(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            remaining_quantity=100,
            submitted_at=utcnow(),
        )

        filled_at = utcnow()
        order.update_fill(filled_quantity=50, average_price=45.5, filled_at=filled_at)

        assert order.filled_quantity == 50
        assert order.remaining_quantity == 50
        assert order.average_fill_price == 45.5
        assert order.total_cost == 2275.0  # 50 * 45.5
        assert order.status == "partially_filled"

    def test_order_update_fill_complete(self) -> None:
        """Test updating order with complete fill."""
        order = Order(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            remaining_quantity=100,
            submitted_at=utcnow(),
        )

        filled_at = utcnow()
        order.update_fill(filled_quantity=100, average_price=45.5, filled_at=filled_at)

        assert order.filled_quantity == 100
        assert order.remaining_quantity == 0
        assert order.status == "filled"
        assert order.filled_at == filled_at

    def test_order_repr(self) -> None:
        """Test Order string representation."""
        order = Order(
            market_id=1,
            ticker="HIGHNYC-25JAN26",
            side="yes",
            action="buy",
            order_type="limit",
            quantity=100,
            remaining_quantity=100,
            status="pending",
            submitted_at=utcnow(),
        )

        repr_str = repr(order)
        assert "HIGHNYC-25JAN26" in repr_str
        assert "yes" in repr_str
        assert "100" in repr_str
        assert "pending" in repr_str


class TestTradeModel:
    """Test suite for Trade model."""

    def test_trade_creation(self) -> None:
        """Test creating a Trade instance."""
        trade = Trade(
            market_id=1,
            ticker="HIGHNYC-25JAN26",
            side="yes",
            action="buy",
            quantity=100,
            price=45.5,
            total_cost=4550.0,
            fees=10.0,
            executed_at=utcnow(),
        )

        assert trade.ticker == "HIGHNYC-25JAN26"
        assert trade.side == "yes"
        assert trade.action == "buy"
        assert trade.quantity == 100
        assert trade.price == 45.5

    def test_trade_notional_value(self) -> None:
        """Test notional value calculation."""
        trade = Trade(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="buy",
            quantity=100,
            price=45.5,
            total_cost=4550.0,
            executed_at=utcnow(),
        )

        assert trade.notional_value == 4550.0  # 100 * 45.5

    def test_trade_calculate_pnl_buy(self) -> None:
        """Test P&L calculation for buy trade."""
        trade = Trade(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="buy",
            quantity=100,
            price=45.0,
            total_cost=4500.0,
            fees=10.0,
            executed_at=utcnow(),
        )

        pnl = trade.calculate_pnl(exit_price=50.0)
        assert pnl == 490.0  # (50 - 45) * 100 - 10

    def test_trade_calculate_pnl_sell(self) -> None:
        """Test P&L calculation for sell trade."""
        trade = Trade(
            market_id=1,
            ticker="TEST-01",
            side="yes",
            action="sell",
            quantity=100,
            price=50.0,
            total_cost=5000.0,
            fees=10.0,
            executed_at=utcnow(),
        )

        pnl = trade.calculate_pnl(exit_price=45.0)
        assert pnl == 490.0  # (50 - 45) * 100 - 10

    def test_trade_repr(self) -> None:
        """Test Trade string representation."""
        trade = Trade(
            market_id=1,
            ticker="HIGHNYC-25JAN26",
            side="yes",
            action="buy",
            quantity=100,
            price=45.5,
            total_cost=4550.0,
            executed_at=utcnow(),
        )

        repr_str = repr(trade)
        assert "HIGHNYC-25JAN26" in repr_str
        assert "yes" in repr_str
        assert "100" in repr_str
        assert "45.5" in repr_str
