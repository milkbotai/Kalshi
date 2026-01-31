"""Tests for PositionRepository class."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestPositionModel:
    """Tests for PositionModel pydantic model."""

    def test_average_entry_price_calculation(self) -> None:
        """Test average_entry_price property."""
        from src.shared.db.repositories.position import PositionModel

        model = PositionModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            fees_paid=10.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Line 53-54: average_entry_price with non-zero quantity
        assert model.average_entry_price == 45.0

    def test_average_entry_price_zero_quantity(self) -> None:
        """Test average_entry_price with zero quantity returns None."""
        from src.shared.db.repositories.position import PositionModel

        model = PositionModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=0,
            entry_price=0.0,
            total_cost=0.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Line 55: return None when quantity is 0
        assert model.average_entry_price is None

    def test_is_long_property(self) -> None:
        """Test is_long property."""
        from src.shared.db.repositories.position import PositionModel

        model = PositionModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Line 60: is_long
        assert model.is_long is True
        assert model.is_short is False

    def test_is_short_property(self) -> None:
        """Test is_short property."""
        from src.shared.db.repositories.position import PositionModel

        model = PositionModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            side="no",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Line 65: is_short
        assert model.is_short is True
        assert model.is_long is False


class TestPositionRepository:
    """Tests for PositionRepository CRUD operations."""

    def _create_mock_db(self) -> MagicMock:
        """Create a mock database manager."""
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)
        return mock_db

    def _create_mock_position(self, **kwargs) -> MagicMock:
        """Create a mock Position ORM object."""
        defaults = {
            "id": 1,
            "ticker": "TEST-TICKER",
            "city_code": "NYC",
            "side": "yes",
            "quantity": 100,
            "entry_price": 45.0,
            "total_cost": 4500.0,
            "fees_paid": 10.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 50.0,
            "is_closed": False,
            "trading_mode": "shadow",
            "opened_at": datetime.now(timezone.utc),
            "closed_at": None,
            "updated_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        mock_pos = MagicMock()
        for k, v in defaults.items():
            setattr(mock_pos, k, v)
        return mock_pos

    def test_init(self) -> None:
        """Test repository initialization."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        # Line 120: super().__init__
        assert repo._db is mock_db

    @patch("src.shared.db.repositories.position.PositionRepository.save")
    def test_open_position(self, mock_save: MagicMock) -> None:
        """Test opening a new position."""
        from src.shared.db.repositories.position import PositionRepository, PositionCreate

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        saved_pos = self._create_mock_position()
        mock_save.return_value = saved_pos

        data = PositionCreate(
            ticker="TEST-TICKER",
            city_code="NYC",
            side="yes",
            quantity=100,
            entry_price=45.0,
            fees_paid=5.0,
            trading_mode="shadow",
        )

        # Lines 131-155: open_position
        result = repo.open_position(data)

        assert result.ticker == "TEST-TICKER"
        assert result.city_code == "NYC"
        mock_save.assert_called_once()

    @patch("src.shared.db.repositories.position.PositionRepository.get_open_position")
    def test_get_or_create_position_existing(self, mock_get_open: MagicMock) -> None:
        """Test get_or_create when position exists."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        existing_pos = PositionModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get_open.return_value = existing_pos

        # Lines 175-177: existing position
        result, created = repo.get_or_create_position("TEST", "NYC", "yes", "shadow")

        assert result is existing_pos
        assert created is False

    @patch("src.shared.db.repositories.position.PositionRepository.save")
    @patch("src.shared.db.repositories.position.PositionRepository.get_open_position")
    def test_get_or_create_position_new(
        self, mock_get_open: MagicMock, mock_save: MagicMock
    ) -> None:
        """Test get_or_create when position doesn't exist."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_get_open.return_value = None
        saved_pos = self._create_mock_position(quantity=0, entry_price=0.0, total_cost=0.0)
        mock_save.return_value = saved_pos

        # Lines 179-192: create new position
        result, created = repo.get_or_create_position("TEST", "NYC", "yes", "shadow")

        assert created is True
        mock_save.assert_called_once()

    @patch("src.shared.db.repositories.position.PositionRepository.save")
    @patch("src.shared.db.repositories.position.PositionRepository.get_open_position")
    def test_get_or_create_position_race_condition(
        self, mock_get_open: MagicMock, mock_save: MagicMock
    ) -> None:
        """Test get_or_create handles race condition."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel
        from sqlalchemy.exc import IntegrityError

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        existing_pos = PositionModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # First call returns None, second (after IntegrityError) returns existing
        mock_get_open.side_effect = [None, existing_pos]
        mock_save.side_effect = IntegrityError("", "", Exception())

        # Lines 193-198: race condition handling
        result, created = repo.get_or_create_position("TEST", "NYC", "yes", "shadow")

        assert result is existing_pos
        assert created is False

    def test_get_open_position_found(self) -> None:
        """Test get_open_position when position exists."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_pos = self._create_mock_position()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_pos

        repo = PositionRepository(mock_db)

        # Lines 216-230: get_open_position
        result = repo.get_open_position("TEST", "NYC", "shadow")

        assert result is not None
        assert result.ticker == "TEST-TICKER"
        mock_session.expunge.assert_called_once_with(mock_pos)

    def test_get_open_position_not_found(self) -> None:
        """Test get_open_position when position doesn't exist."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        repo = PositionRepository(mock_db)

        result = repo.get_open_position("TEST", "NYC", "shadow")

        assert result is None

    def test_get_all_open_positions(self) -> None:
        """Test get_all_open_positions."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_pos1 = self._create_mock_position(id=1)
        mock_pos2 = self._create_mock_position(id=2)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_pos1, mock_pos2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = PositionRepository(mock_db)

        # Lines 246-261: get_all_open_positions with filters
        results = repo.get_all_open_positions(city_code="NYC", trading_mode="shadow")

        assert len(results) == 2

    @patch("src.shared.db.repositories.position.PositionRepository._get_position_model")
    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_add_to_position(
        self, mock_get_by_id: MagicMock, mock_get_model: MagicMock
    ) -> None:
        """Test add_to_position."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_pos = self._create_mock_position()
        mock_get_by_id.return_value = mock_pos

        updated_model = PositionModel(
            id=1,
            ticker="TEST-TICKER",
            city_code="NYC",
            side="yes",
            quantity=150,
            entry_price=45.33,
            total_cost=6800.0,
            fees_paid=15.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get_model.return_value = updated_model

        # Lines 283-317: add_to_position
        result = repo.add_to_position(1, 50, 46.0, 5.0)

        assert result is not None
        assert result.quantity == 150

    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_add_to_position_not_found(self, mock_get_by_id: MagicMock) -> None:
        """Test add_to_position when position not found."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_get_by_id.return_value = None

        result = repo.add_to_position(999, 50, 46.0)

        assert result is None

    @patch("src.shared.db.repositories.position.PositionRepository._get_position_model")
    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_reduce_position_partial(
        self, mock_get_by_id: MagicMock, mock_get_model: MagicMock
    ) -> None:
        """Test reduce_position partial close."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_pos = self._create_mock_position(
            quantity=100,
            total_cost=4500.0,
            side="yes",
            realized_pnl=0.0,
            fees_paid=0.0,
        )
        mock_get_by_id.return_value = mock_pos

        updated_model = PositionModel(
            id=1,
            ticker="TEST-TICKER",
            city_code="NYC",
            side="yes",
            quantity=50,
            entry_price=45.0,
            total_cost=2250.0,
            fees_paid=5.0,
            realized_pnl=250.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get_model.return_value = updated_model

        # Lines 337-390: reduce_position (partial)
        result, pnl = repo.reduce_position(1, 50, 50.0, 5.0)

        assert result is not None
        assert pnl > 0  # Profit on long position with higher exit price

    @patch("src.shared.db.repositories.position.PositionRepository._get_position_model")
    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_reduce_position_short(
        self, mock_get_by_id: MagicMock, mock_get_model: MagicMock
    ) -> None:
        """Test reduce_position for short position."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        # Short position
        mock_pos = self._create_mock_position(
            quantity=100,
            total_cost=5500.0,
            side="no",  # Short
            realized_pnl=0.0,
            fees_paid=0.0,
        )
        mock_get_by_id.return_value = mock_pos

        updated_model = PositionModel(
            id=1,
            ticker="TEST-TICKER",
            city_code="NYC",
            side="no",
            quantity=50,
            entry_price=55.0,
            total_cost=2750.0,
            fees_paid=5.0,
            realized_pnl=250.0,
            unrealized_pnl=0.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get_model.return_value = updated_model

        # Line 348-349: short position P&L calculation
        result, pnl = repo.reduce_position(1, 50, 50.0, 5.0)

        assert result is not None
        # Short: profit when entry > exit (55 > 50)
        assert pnl > 0

    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_reduce_position_not_found(self, mock_get_by_id: MagicMock) -> None:
        """Test reduce_position when position not found."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_get_by_id.return_value = None

        result, pnl = repo.reduce_position(999, 50, 50.0)

        assert result is None
        assert pnl == 0.0

    @patch("src.shared.db.repositories.position.PositionRepository.reduce_position")
    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_close_position(
        self, mock_get_by_id: MagicMock, mock_reduce: MagicMock
    ) -> None:
        """Test close_position."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_pos = self._create_mock_position(quantity=100, is_closed=False)
        mock_get_by_id.return_value = mock_pos

        closed_model = PositionModel(
            id=1,
            ticker="TEST-TICKER",
            city_code="NYC",
            side="yes",
            quantity=0,
            entry_price=45.0,
            total_cost=0.0,
            fees_paid=10.0,
            realized_pnl=500.0,
            unrealized_pnl=0.0,
            is_closed=True,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            closed_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_reduce.return_value = (closed_model, 500.0)

        # Lines 408-417: close_position
        result, pnl = repo.close_position(1, 50.0, 5.0)

        assert result is not None
        assert pnl == 500.0
        mock_reduce.assert_called_once_with(
            position_id=1, quantity=100, exit_price=50.0, fees=5.0
        )

    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_close_position_not_found(self, mock_get_by_id: MagicMock) -> None:
        """Test close_position when position not found or already closed."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_get_by_id.return_value = None

        # Lines 408-410: close_position when not found
        result, pnl = repo.close_position(999, 50.0)

        assert result is None
        assert pnl == 0.0

    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_close_position_already_closed(self, mock_get_by_id: MagicMock) -> None:
        """Test close_position when position already closed."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_pos = self._create_mock_position(is_closed=True)
        mock_get_by_id.return_value = mock_pos

        result, pnl = repo.close_position(1, 50.0)

        assert result is None
        assert pnl == 0.0

    @patch("src.shared.db.repositories.position.PositionRepository._get_position_model")
    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_update_unrealized_pnl_long(
        self, mock_get_by_id: MagicMock, mock_get_model: MagicMock
    ) -> None:
        """Test update_unrealized_pnl for long position."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_pos = self._create_mock_position(
            quantity=100, total_cost=4500.0, side="yes", is_closed=False
        )
        mock_get_by_id.return_value = mock_pos

        updated_model = PositionModel(
            id=1,
            ticker="TEST-TICKER",
            city_code="NYC",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=500.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get_model.return_value = updated_model

        # Lines 433-457: update_unrealized_pnl long position
        result = repo.update_unrealized_pnl(1, 50.0)

        assert result is not None
        assert result.unrealized_pnl == 500.0

    @patch("src.shared.db.repositories.position.PositionRepository._get_position_model")
    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_update_unrealized_pnl_short(
        self, mock_get_by_id: MagicMock, mock_get_model: MagicMock
    ) -> None:
        """Test update_unrealized_pnl for short position."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        # Short position
        mock_pos = self._create_mock_position(
            quantity=100, total_cost=5500.0, side="no", is_closed=False
        )
        mock_get_by_id.return_value = mock_pos

        updated_model = PositionModel(
            id=1,
            ticker="TEST-TICKER",
            city_code="NYC",
            side="no",
            quantity=100,
            entry_price=55.0,
            total_cost=5500.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=500.0,
            is_closed=False,
            trading_mode="shadow",
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_get_model.return_value = updated_model

        # Lines 441-442: short position unrealized P&L
        result = repo.update_unrealized_pnl(1, 50.0)

        assert result is not None

    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_update_unrealized_pnl_not_found(self, mock_get_by_id: MagicMock) -> None:
        """Test update_unrealized_pnl when position not found."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_get_by_id.return_value = None

        result = repo.update_unrealized_pnl(999, 50.0)

        assert result is None

    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_update_unrealized_pnl_closed(self, mock_get_by_id: MagicMock) -> None:
        """Test update_unrealized_pnl when position is closed."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_pos = self._create_mock_position(is_closed=True)
        mock_get_by_id.return_value = mock_pos

        result = repo.update_unrealized_pnl(1, 50.0)

        assert result is None

    def test_get_position_summary(self) -> None:
        """Test get_position_summary."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        # Mock open positions result
        mock_open_row = (5, 500, 25000.0, 1000.0)
        # Mock closed positions result
        mock_closed_row = (10, 5000.0, 100.0)

        mock_session.execute.return_value.one.side_effect = [mock_open_row, mock_closed_row]

        repo = PositionRepository(mock_db)

        # Lines 473-513: get_position_summary
        result = repo.get_position_summary(city_code="NYC", trading_mode="shadow")

        assert result["open_positions"] == 5
        assert result["open_quantity"] == 500
        assert result["open_cost"] == 25000.0
        assert result["unrealized_pnl"] == 1000.0
        assert result["closed_positions"] == 10
        assert result["realized_pnl"] == 5000.0
        assert result["total_fees"] == 100.0

    def test_get_position_summary_null_values(self) -> None:
        """Test get_position_summary with null values."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        # Mock with None values
        mock_open_row = (0, None, None, None)
        mock_closed_row = (0, None, None)

        mock_session.execute.return_value.one.side_effect = [mock_open_row, mock_closed_row]

        repo = PositionRepository(mock_db)

        result = repo.get_position_summary()

        assert result["open_positions"] == 0
        assert result["open_quantity"] == 0
        assert result["open_cost"] == 0.0

    def test_get_positions_by_city(self) -> None:
        """Test get_positions_by_city."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_pos1 = self._create_mock_position(id=1, city_code="NYC")
        mock_pos2 = self._create_mock_position(id=2, city_code="NYC")
        mock_pos3 = self._create_mock_position(id=3, city_code="LAX")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_pos1, mock_pos2, mock_pos3]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = PositionRepository(mock_db)

        # Lines 527-548: get_positions_by_city
        result = repo.get_positions_by_city(include_closed=True)

        assert "NYC" in result
        assert "LAX" in result
        assert len(result["NYC"]) == 2
        assert len(result["LAX"]) == 1

    def test_get_pnl_by_city(self) -> None:
        """Test get_pnl_by_city."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("NYC", 1500.0),
            ("LAX", -200.0),
            ("CHI", None),
        ]

        repo = PositionRepository(mock_db)

        # Lines 559-574: get_pnl_by_city
        result = repo.get_pnl_by_city(include_unrealized=True)

        assert result["NYC"] == 1500.0
        assert result["LAX"] == -200.0
        assert result["CHI"] == 0.0

    def test_get_pnl_by_city_realized_only(self) -> None:
        """Test get_pnl_by_city with realized only."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("NYC", 1000.0),
        ]

        repo = PositionRepository(mock_db)

        # Lines 562-565: include_unrealized=False
        result = repo.get_pnl_by_city(include_unrealized=False)

        assert result["NYC"] == 1000.0

    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_get_position_model_found(self, mock_get_by_id: MagicMock) -> None:
        """Test _get_position_model when found."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_pos = self._create_mock_position()
        mock_get_by_id.return_value = mock_pos

        # Lines 585-588: _get_position_model
        result = repo._get_position_model(1)

        assert result is not None
        assert result.id == 1

    @patch("src.shared.db.repositories.position.PositionRepository.get_by_id")
    def test_get_position_model_not_found(self, mock_get_by_id: MagicMock) -> None:
        """Test _get_position_model when not found."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = self._create_mock_db()
        repo = PositionRepository(mock_db)

        mock_get_by_id.return_value = None

        result = repo._get_position_model(999)

        assert result is None
