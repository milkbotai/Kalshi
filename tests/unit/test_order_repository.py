"""Tests for OrderRepository class."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestOrderModel:
    """Tests for OrderModel pydantic model."""

    def test_is_filled_property(self) -> None:
        """Test is_filled property."""
        from src.shared.db.repositories.order import OrderModel

        model = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="filled",
            remaining_quantity=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Line 65: is_filled
        assert model.is_filled is True

    def test_is_open_property_true(self) -> None:
        """Test is_open property returns True for open statuses."""
        from src.shared.db.repositories.order import OrderModel

        for status in ["pending", "submitted", "resting", "partially_filled"]:
            model = OrderModel(
                id=1,
                intent_key="test-key",
                ticker="TEST",
                city_code="NYC",
                side="yes",
                action="buy",
                quantity=100,
                limit_price=45.0,
                status=status,
                remaining_quantity=100,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            # Lines 70-75: is_open
            assert model.is_open is True

    def test_is_open_property_false(self) -> None:
        """Test is_open property returns False for closed statuses."""
        from src.shared.db.repositories.order import OrderModel

        for status in ["filled", "cancelled", "rejected"]:
            model = OrderModel(
                id=1,
                intent_key="test-key",
                ticker="TEST",
                city_code="NYC",
                side="yes",
                action="buy",
                quantity=100,
                limit_price=45.0,
                status=status,
                remaining_quantity=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            assert model.is_open is False


class TestOrderRepository:
    """Tests for OrderRepository CRUD operations."""

    def _create_mock_db(self) -> MagicMock:
        """Create a mock database manager."""
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)
        return mock_db

    def _create_mock_order(self, **kwargs) -> MagicMock:
        """Create a mock Order ORM object."""
        defaults = {
            "id": 1,
            "intent_key": "test-intent-key",
            "ticker": "TEST-TICKER",
            "city_code": "NYC",
            "market_id": None,
            "event_date": None,
            "signal_id": None,
            "kalshi_order_id": "kalshi-123",
            "client_order_id": None,
            "side": "yes",
            "action": "buy",
            "quantity": 100,
            "limit_price": 45.0,
            "status": "pending",
            "filled_quantity": 0,
            "remaining_quantity": 100,
            "average_fill_price": None,
            "signal_p_yes": 0.55,
            "signal_edge": 0.05,
            "trading_mode": "shadow",
            "status_message": None,
            "created_at": datetime.now(timezone.utc),
            "submitted_at": None,
            "filled_at": None,
            "cancelled_at": None,
            "updated_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        mock_order = MagicMock()
        for k, v in defaults.items():
            setattr(mock_order, k, v)
        return mock_order

    def test_init(self) -> None:
        """Test repository initialization."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        # Line 139: super().__init__
        assert repo._db is mock_db

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_create_order_idempotent_existing(self, mock_get: MagicMock) -> None:
        """Test create_order_idempotent when order exists."""
        from src.shared.db.repositories.order import OrderRepository, OrderCreate, OrderModel

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        existing_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="pending",
            remaining_quantity=100,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get.return_value = existing_order

        data = OrderCreate(
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            limit_price=45.0,
        )

        # Lines 156-163: existing order
        result, created = repo.create_order_idempotent(data)

        assert created is False
        assert result is existing_order

    @patch("src.shared.db.repositories.order.OrderRepository.save")
    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_create_order_idempotent_new(
        self, mock_get: MagicMock, mock_save: MagicMock
    ) -> None:
        """Test create_order_idempotent creates new order."""
        from src.shared.db.repositories.order import OrderRepository, OrderCreate

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        mock_get.return_value = None
        saved_order = self._create_mock_order()
        mock_save.return_value = saved_order

        data = OrderCreate(
            intent_key="new-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            limit_price=45.0,
        )

        # Lines 165-194: create new order
        result, created = repo.create_order_idempotent(data)

        assert created is True
        mock_save.assert_called_once()

    @patch("src.shared.db.repositories.order.OrderRepository.save")
    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_create_order_idempotent_race_condition(
        self, mock_get: MagicMock, mock_save: MagicMock
    ) -> None:
        """Test create_order_idempotent handles race condition."""
        from src.shared.db.repositories.order import OrderRepository, OrderCreate, OrderModel
        from sqlalchemy.exc import IntegrityError

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        existing_order = OrderModel(
            id=1,
            intent_key="race-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="pending",
            remaining_quantity=100,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # First call returns None, second returns existing (after race)
        mock_get.side_effect = [None, existing_order]
        mock_save.side_effect = IntegrityError("", "", Exception())

        data = OrderCreate(
            intent_key="race-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            limit_price=45.0,
        )

        # Lines 196-205: race condition handling
        result, created = repo.create_order_idempotent(data)

        assert created is False
        assert result is existing_order

    def test_get_by_intent_key_found(self) -> None:
        """Test get_by_intent_key when order exists."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_order = self._create_mock_order()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_order

        repo = OrderRepository(mock_db)

        # Lines 216-223: get_by_intent_key
        result = repo.get_by_intent_key("test-intent-key")

        assert result is not None
        assert result.intent_key == "test-intent-key"
        mock_session.expunge.assert_called_once_with(mock_order)

    def test_get_by_intent_key_not_found(self) -> None:
        """Test get_by_intent_key when order doesn't exist."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        repo = OrderRepository(mock_db)

        result = repo.get_by_intent_key("nonexistent")

        assert result is None

    def test_get_by_kalshi_id_found(self) -> None:
        """Test get_by_kalshi_id when order exists."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_order = self._create_mock_order()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_order

        repo = OrderRepository(mock_db)

        # Lines 234-241: get_by_kalshi_id
        result = repo.get_by_kalshi_id("kalshi-123")

        assert result is not None
        mock_session.expunge.assert_called_once()

    def test_get_by_kalshi_id_not_found(self) -> None:
        """Test get_by_kalshi_id when order doesn't exist."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        repo = OrderRepository(mock_db)

        result = repo.get_by_kalshi_id("nonexistent")

        assert result is None

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_update_status_submitted(self, mock_get: MagicMock) -> None:
        """Test update_status to submitted."""
        from src.shared.db.repositories.order import OrderRepository, OrderModel

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        updated_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="submitted",
            remaining_quantity=100,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get.return_value = updated_order

        # Lines 261-295: update_status with submitted
        result = repo.update_status(
            intent_key="test-key",
            new_status="submitted",
            kalshi_order_id="kalshi-456",
            status_message="Order submitted",
        )

        assert result is not None
        assert result.status == "submitted"

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_update_status_filled(self, mock_get: MagicMock) -> None:
        """Test update_status to filled."""
        from src.shared.db.repositories.order import OrderRepository, OrderModel

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        updated_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="filled",
            remaining_quantity=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get.return_value = updated_order

        # Line 281-282: filled status timestamp
        result = repo.update_status(intent_key="test-key", new_status="filled")

        assert result is not None

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_update_status_cancelled(self, mock_get: MagicMock) -> None:
        """Test update_status to cancelled."""
        from src.shared.db.repositories.order import OrderRepository, OrderModel

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        updated_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="cancelled",
            remaining_quantity=100,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get.return_value = updated_order

        # Lines 283-284: cancelled/rejected timestamp
        result = repo.update_status(intent_key="test-key", new_status="cancelled")

        assert result is not None

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_record_fill_first_fill(self, mock_get: MagicMock) -> None:
        """Test record_fill for first fill."""
        from src.shared.db.repositories.order import OrderRepository, OrderModel

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        # Initial order
        initial_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="submitted",
            filled_quantity=0,
            remaining_quantity=100,
            average_fill_price=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Updated order after fill
        updated_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="partially_filled",
            filled_quantity=50,
            remaining_quantity=50,
            average_fill_price=46.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_get.side_effect = [initial_order, updated_order]

        # Lines 315-369: record_fill
        result = repo.record_fill("test-key", fill_quantity=50, fill_price=46.0)

        assert result is not None

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_record_fill_subsequent_fill(self, mock_get: MagicMock) -> None:
        """Test record_fill for subsequent fill with weighted average."""
        from src.shared.db.repositories.order import OrderRepository, OrderModel

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        # Order with previous fills
        initial_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="partially_filled",
            filled_quantity=50,
            remaining_quantity=50,
            average_fill_price=45.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        updated_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="filled",
            filled_quantity=100,
            remaining_quantity=0,
            average_fill_price=46.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_get.side_effect = [initial_order, updated_order]

        # Lines 325-329: weighted average calculation
        result = repo.record_fill("test-key", fill_quantity=50, fill_price=47.0)

        assert result is not None

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_record_fill_not_found(self, mock_get: MagicMock) -> None:
        """Test record_fill when order not found."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        mock_get.return_value = None

        result = repo.record_fill("nonexistent", fill_quantity=50, fill_price=46.0)

        assert result is None

    def test_get_open_orders(self) -> None:
        """Test get_open_orders."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_order1 = self._create_mock_order(id=1, status="pending")
        mock_order2 = self._create_mock_order(id=2, status="submitted")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_order1, mock_order2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = OrderRepository(mock_db)

        # Lines 385-407: get_open_orders with filters
        results = repo.get_open_orders(city_code="NYC", trading_mode="shadow")

        assert len(results) == 2

    def test_get_orders_by_status(self) -> None:
        """Test get_orders_by_status."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_order = self._create_mock_order(status="filled")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_order]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = OrderRepository(mock_db)

        # Lines 425-438: get_orders_by_status
        results = repo.get_orders_by_status("filled", city_code="NYC", limit=50)

        assert len(results) == 1

    def test_get_orders_for_ticker(self) -> None:
        """Test get_orders_for_ticker."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_order = self._create_mock_order()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_order]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = OrderRepository(mock_db)

        # Lines 456-475: get_orders_for_ticker
        results = repo.get_orders_for_ticker("TEST-TICKER", include_closed=False)

        assert len(results) == 1

    def test_get_orders_for_ticker_include_closed(self) -> None:
        """Test get_orders_for_ticker with closed orders."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = OrderRepository(mock_db)

        # Line 459-466: include_closed=True skips status filter
        results = repo.get_orders_for_ticker("TEST-TICKER", include_closed=True)

        assert len(results) == 0

    def test_get_recent_orders(self) -> None:
        """Test get_recent_orders."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_order1 = self._create_mock_order(id=1)
        mock_order2 = self._create_mock_order(id=2)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_order1, mock_order2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = OrderRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=7)
        end_time = datetime.now(timezone.utc)

        # Lines 497-516: get_recent_orders with all filters
        results = repo.get_recent_orders(
            city_code="NYC",
            trading_mode="shadow",
            start_time=start_time,
            end_time=end_time,
            limit=50,
        )

        assert len(results) == 2

    @patch("src.shared.db.repositories.order.OrderRepository.update_status")
    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_cancel_order(self, mock_get: MagicMock, mock_update: MagicMock) -> None:
        """Test cancel_order."""
        from src.shared.db.repositories.order import OrderRepository, OrderModel

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        open_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="pending",
            remaining_quantity=100,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get.return_value = open_order

        cancelled_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="cancelled",
            remaining_quantity=100,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_update.return_value = cancelled_order

        # Lines 528-536: cancel_order
        result = repo.cancel_order("test-key", reason="Test cancel")

        assert result is not None
        mock_update.assert_called_once()

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_cancel_order_not_found(self, mock_get: MagicMock) -> None:
        """Test cancel_order when order not found."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        mock_get.return_value = None

        # Lines 528-530: cancel_order not found
        result = repo.cancel_order("nonexistent")

        assert result is None

    @patch("src.shared.db.repositories.order.OrderRepository.get_by_intent_key")
    def test_cancel_order_already_closed(self, mock_get: MagicMock) -> None:
        """Test cancel_order when order already closed."""
        from src.shared.db.repositories.order import OrderRepository, OrderModel

        mock_db = self._create_mock_db()
        repo = OrderRepository(mock_db)

        closed_order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status="filled",
            remaining_quantity=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get.return_value = closed_order

        result = repo.cancel_order("test-key")

        assert result is None

    def test_get_order_stats(self) -> None:
        """Test get_order_stats."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        # Mock status counts
        mock_session.execute.return_value.all.return_value = [
            ("filled", 50),
            ("pending", 30),
            ("cancelled", 20),
        ]
        # Mock volume
        mock_session.execute.return_value.scalar.return_value = 10000

        repo = OrderRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=30)
        end_time = datetime.now(timezone.utc)

        # Lines 554-602: get_order_stats with all filters
        result = repo.get_order_stats(
            city_code="NYC",
            start_time=start_time,
            end_time=end_time,
        )

        assert "total_orders" in result
        assert "by_status" in result
        assert "total_volume" in result
        assert "fill_rate" in result

    def test_get_order_stats_no_filters(self) -> None:
        """Test get_order_stats without filters."""
        from src.shared.db.repositories.order import OrderRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = []
        mock_session.execute.return_value.scalar.return_value = 0

        repo = OrderRepository(mock_db)

        result = repo.get_order_stats()

        assert result["total_orders"] == 0
        assert result["total_volume"] == 0
