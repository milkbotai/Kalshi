"""Unit tests for Order Management System."""

from datetime import datetime, timedelta

import pytest

from src.trader.oms import OrderManagementSystem, OrderState
from src.trader.strategy import Signal


class TestOrderManagementSystem:
    """Test suite for OrderManagementSystem."""

    @pytest.fixture
    def oms(self) -> OrderManagementSystem:
        """Create OMS instance."""
        return OrderManagementSystem()

    @pytest.fixture
    def sample_signal(self) -> Signal:
        """Create sample signal."""
        return Signal(
            ticker="HIGHNYC-25JAN26",
            p_yes=0.65,
            uncertainty=0.10,
            edge=5.0,
            decision="BUY",
            side="yes",
        )

    def test_oms_initialization(self, oms: OrderManagementSystem) -> None:
        """Test OMS initializes correctly."""
        assert oms is not None
        assert len(oms.get_all_orders()) == 0

    def test_generate_intent_key_deterministic(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test intent key generation is deterministic."""
        key1 = oms.generate_intent_key(sample_signal, "NYC", 123, "2026-01-26")
        key2 = oms.generate_intent_key(sample_signal, "NYC", 123, "2026-01-26")

        assert key1 == key2
        assert len(key1) == 16  # SHA256 truncated to 16 chars

    def test_generate_intent_key_different_inputs(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test different inputs produce different intent keys."""
        key1 = oms.generate_intent_key(sample_signal, "NYC", 123, "2026-01-26")
        key2 = oms.generate_intent_key(sample_signal, "CHI", 123, "2026-01-26")
        key3 = oms.generate_intent_key(sample_signal, "NYC", 456, "2026-01-26")

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_submit_order_creates_new_order(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test submitting order creates new order."""
        order = oms.submit_order(
            signal=sample_signal,
            city_code="NYC",
            market_id=123,
            event_date="2026-01-26",
            quantity=100,
            limit_price=45.0,
        )

        assert order is not None
        assert order["ticker"] == "HIGHNYC-25JAN26"
        assert order["side"] == "yes"
        assert order["quantity"] == 100
        assert order["limit_price"] == 45.0
        assert order["status"] == OrderState.PENDING
        assert order["intent_key"] is not None

    def test_submit_order_duplicate_returns_existing(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test submitting duplicate order returns existing order."""
        # Submit first order
        order1 = oms.submit_order(
            signal=sample_signal,
            city_code="NYC",
            market_id=123,
            event_date="2026-01-26",
            quantity=100,
            limit_price=45.0,
        )

        # Submit duplicate
        order2 = oms.submit_order(
            signal=sample_signal,
            city_code="NYC",
            market_id=123,
            event_date="2026-01-26",
            quantity=100,
            limit_price=45.0,
        )

        # Should return same order
        assert order1 is order2
        assert order1["intent_key"] == order2["intent_key"]

        # Should only have one order
        assert len(oms.get_all_orders()) == 1

    def test_update_order_status_success(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test updating order status."""
        order = oms.submit_order(
            signal=sample_signal,
            city_code="NYC",
            market_id=123,
            event_date="2026-01-26",
            quantity=100,
            limit_price=45.0,
        )

        intent_key = order["intent_key"]
        result = oms.update_order_status(
            intent_key=intent_key,
            status=OrderState.SUBMITTED,
            kalshi_order_id="order_123",
        )

        assert result is True
        assert order["status"] == OrderState.SUBMITTED
        assert order["kalshi_order_id"] == "order_123"
        assert order["submitted_at"] is not None

    def test_update_order_status_not_found(self, oms: OrderManagementSystem) -> None:
        """Test updating non-existent order returns False."""
        result = oms.update_order_status(
            intent_key="nonexistent",
            status=OrderState.FILLED,
        )

        assert result is False

    def test_update_order_status_sets_timestamps(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test status updates set appropriate timestamps."""
        order = oms.submit_order(
            signal=sample_signal,
            city_code="NYC",
            market_id=123,
            event_date="2026-01-26",
            quantity=100,
            limit_price=45.0,
        )

        intent_key = order["intent_key"]

        # Update to SUBMITTED
        oms.update_order_status(intent_key, OrderState.SUBMITTED)
        assert order["submitted_at"] is not None

        # Update to FILLED
        oms.update_order_status(intent_key, OrderState.FILLED)
        assert order["filled_at"] is not None

    def test_get_order_by_intent_key(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test retrieving order by intent key."""
        order = oms.submit_order(
            signal=sample_signal,
            city_code="NYC",
            market_id=123,
            event_date="2026-01-26",
            quantity=100,
            limit_price=45.0,
        )

        intent_key = order["intent_key"]
        retrieved = oms.get_order_by_intent_key(intent_key)

        assert retrieved is not None
        assert retrieved is order

    def test_get_order_by_intent_key_not_found(self, oms: OrderManagementSystem) -> None:
        """Test retrieving non-existent order returns None."""
        retrieved = oms.get_order_by_intent_key("nonexistent")

        assert retrieved is None

    def test_get_all_orders(self, oms: OrderManagementSystem, sample_signal: Signal) -> None:
        """Test retrieving all orders."""
        # Create multiple orders
        oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        oms.submit_order(sample_signal, "CHI", 456, "2026-01-26", 50, 50.0)

        orders = oms.get_all_orders()

        assert len(orders) == 2

    def test_get_orders_by_status(self, oms: OrderManagementSystem, sample_signal: Signal) -> None:
        """Test filtering orders by status."""
        # Create orders with different statuses
        order1 = oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        order2 = oms.submit_order(sample_signal, "CHI", 456, "2026-01-26", 50, 50.0)

        # Update one to SUBMITTED
        oms.update_order_status(order1["intent_key"], OrderState.SUBMITTED)

        # Filter by status
        pending_orders = oms.get_orders_by_status(OrderState.PENDING)
        submitted_orders = oms.get_orders_by_status(OrderState.SUBMITTED)

        assert len(pending_orders) == 1
        assert len(submitted_orders) == 1
        assert pending_orders[0] is order2
        assert submitted_orders[0] is order1

    def test_reconcile_fills_matches_by_order_id(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test reconciliation matches fills to orders by kalshi_order_id."""
        # Create order and set kalshi_order_id
        order = oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        oms.update_order_status(
            order["intent_key"],
            OrderState.SUBMITTED,
            kalshi_order_id="order_123",
        )

        # Reconcile with fill
        fills = [
            {
                "order_id": "order_123",
                "count": 100,
                "yes_price": 45,
                "created_time": "2026-01-25T12:00:00Z",
            }
        ]

        summary = oms.reconcile_fills(fills)

        assert summary["matched_count"] == 1
        assert summary["orphaned_count"] == 0
        assert order["status"] == OrderState.FILLED
        assert order["filled_quantity"] == 100
        assert order["average_fill_price"] == 45

    def test_reconcile_fills_partial_fill(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test reconciliation with partial fill."""
        order = oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        oms.update_order_status(
            order["intent_key"],
            OrderState.SUBMITTED,
            kalshi_order_id="order_123",
        )

        # Partial fill
        fills = [
            {
                "order_id": "order_123",
                "count": 50,
                "yes_price": 45,
                "created_time": "2026-01-25T12:00:00Z",
            }
        ]

        summary = oms.reconcile_fills(fills)

        assert summary["matched_count"] == 1
        assert order["status"] == OrderState.PARTIALLY_FILLED
        assert order["filled_quantity"] == 50
        assert order["remaining_quantity"] == 50

    def test_reconcile_fills_multiple_fills_same_order(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test reconciliation with multiple fills for same order."""
        order = oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        oms.update_order_status(
            order["intent_key"],
            OrderState.SUBMITTED,
            kalshi_order_id="order_123",
        )

        # Multiple fills
        fills = [
            {
                "order_id": "order_123",
                "count": 30,
                "yes_price": 44,
                "created_time": "2026-01-25T12:00:00Z",
            },
            {
                "order_id": "order_123",
                "count": 70,
                "yes_price": 46,
                "created_time": "2026-01-25T12:05:00Z",
            },
        ]

        summary = oms.reconcile_fills(fills)

        assert summary["matched_count"] == 2
        assert order["status"] == OrderState.FILLED
        assert order["filled_quantity"] == 100
        # Average price: (30*44 + 70*46) / 100 = 45.4
        assert 45.3 <= order["average_fill_price"] <= 45.5

    def test_reconcile_fills_detects_orphaned(self, oms: OrderManagementSystem) -> None:
        """Test reconciliation detects orphaned fills."""
        # No local orders created
        fills = [
            {
                "order_id": "unknown_order",
                "count": 50,
                "yes_price": 45,
                "created_time": "2026-01-25T12:00:00Z",
            }
        ]

        summary = oms.reconcile_fills(fills)

        assert summary["matched_count"] == 0
        assert summary["orphaned_count"] == 1
        assert len(summary["orphaned_fills"]) == 1

    def test_reconcile_fills_filters_by_timestamp(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test reconciliation filters fills by timestamp."""
        order = oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        oms.update_order_status(
            order["intent_key"],
            OrderState.SUBMITTED,
            kalshi_order_id="order_123",
        )

        # Old fill (before cutoff)
        old_time = datetime.utcnow() - timedelta(hours=2)
        since_timestamp = datetime.utcnow() - timedelta(hours=1)

        fills = [
            {
                "order_id": "order_123",
                "count": 50,
                "yes_price": 45,
                "created_time": old_time.isoformat() + "Z",
            }
        ]

        summary = oms.reconcile_fills(fills, since_timestamp=since_timestamp)

        # Should skip old fill
        assert summary["matched_count"] == 0
        assert order["filled_quantity"] == 0

    def test_reconcile_fills_empty_list(self, oms: OrderManagementSystem) -> None:
        """Test reconciliation with empty fill list."""
        summary = oms.reconcile_fills([])

        assert summary["total_fills"] == 0
        assert summary["matched_count"] == 0
        assert summary["orphaned_count"] == 0

    def test_order_state_transitions(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test order state machine transitions."""
        order = oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        intent_key = order["intent_key"]

        # PENDING -> SUBMITTED
        assert order["status"] == OrderState.PENDING
        oms.update_order_status(intent_key, OrderState.SUBMITTED, kalshi_order_id="order_123")
        assert order["status"] == OrderState.SUBMITTED

        # SUBMITTED -> PARTIALLY_FILLED (via reconciliation)
        fills = [
            {
                "order_id": "order_123",
                "count": 50,
                "yes_price": 45,
                "created_time": "2026-01-25T12:00:00Z",
            }
        ]
        oms.reconcile_fills(fills)
        assert order["status"] == OrderState.PARTIALLY_FILLED

        # PARTIALLY_FILLED -> FILLED (via reconciliation)
        fills = [
            {
                "order_id": "order_123",
                "count": 50,
                "yes_price": 45,
                "created_time": "2026-01-25T12:05:00Z",
            }
        ]
        oms.reconcile_fills(fills)
        assert order["status"] == OrderState.FILLED

    def test_reconcile_fills_handles_missing_price(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test reconciliation handles fills with missing price."""
        order = oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        oms.update_order_status(
            order["intent_key"],
            OrderState.SUBMITTED,
            kalshi_order_id="order_123",
        )

        # Fill with no price
        fills = [
            {
                "order_id": "order_123",
                "count": 100,
                "created_time": "2026-01-25T12:00:00Z",
            }
        ]

        summary = oms.reconcile_fills(fills)

        assert summary["matched_count"] == 1
        assert order["average_fill_price"] == 0  # Default to 0

    def test_reconcile_fills_handles_invalid_timestamp(
        self, oms: OrderManagementSystem, sample_signal: Signal
    ) -> None:
        """Test reconciliation handles invalid timestamp format."""
        order = oms.submit_order(sample_signal, "NYC", 123, "2026-01-26", 100, 45.0)
        oms.update_order_status(
            order["intent_key"],
            OrderState.SUBMITTED,
            kalshi_order_id="order_123",
        )

        # Fill with invalid timestamp
        fills = [
            {
                "order_id": "order_123",
                "count": 100,
                "yes_price": 45,
                "created_time": "invalid",
            }
        ]

        summary = oms.reconcile_fills(fills)

        # Should still match, using current time
        assert summary["matched_count"] == 1
