"""Tests for FillRepository class."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestFillRepository:
    """Tests for FillRepository CRUD operations."""

    def _create_mock_db(self) -> MagicMock:
        """Create a mock database manager."""
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)
        return mock_db

    def _create_mock_fill(self, **kwargs) -> MagicMock:
        """Create a mock Fill ORM object."""
        defaults = {
            "id": 1,
            "order_id": 100,
            "kalshi_fill_id": "fill-123",
            "kalshi_order_id": "order-456",
            "ticker": "TEST-TICKER",
            "city_code": "NYC",
            "side": "yes",
            "action": "buy",
            "quantity": 50,
            "price": 45.0,
            "notional_value": 2250.0,
            "fees": 5.0,
            "realized_pnl": 100.0,
            "trading_mode": "shadow",
            "fill_time": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        mock_fill = MagicMock()
        for k, v in defaults.items():
            setattr(mock_fill, k, v)
        return mock_fill

    def test_init(self) -> None:
        """Test repository initialization."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        repo = FillRepository(mock_db)

        # Line 99: super().__init__
        assert repo._db is mock_db

    @patch("src.shared.db.repositories.fill.FillRepository.save")
    def test_save_fill(self, mock_save: MagicMock) -> None:
        """Test saving a new fill."""
        from src.shared.db.repositories.fill import FillRepository, FillCreate

        mock_db = self._create_mock_db()
        repo = FillRepository(mock_db)

        saved_fill = self._create_mock_fill()
        mock_save.return_value = saved_fill

        data = FillCreate(
            order_id=100,
            kalshi_fill_id="fill-123",
            kalshi_order_id="order-456",
            ticker="TEST-TICKER",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=50,
            price=45.0,
            fees=5.0,
            realized_pnl=100.0,
            trading_mode="shadow",
        )

        # Lines 110-141: save_fill
        result = repo.save_fill(data)

        assert result.ticker == "TEST-TICKER"
        assert result.order_id == 100
        mock_save.assert_called_once()

    @patch("src.shared.db.repositories.fill.FillRepository.save")
    def test_save_fill_with_fill_time(self, mock_save: MagicMock) -> None:
        """Test saving a fill with explicit fill_time."""
        from src.shared.db.repositories.fill import FillRepository, FillCreate

        mock_db = self._create_mock_db()
        repo = FillRepository(mock_db)

        fill_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        saved_fill = self._create_mock_fill(fill_time=fill_time)
        mock_save.return_value = saved_fill

        data = FillCreate(
            order_id=100,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=50,
            price=45.0,
            fill_time=fill_time,
        )

        result = repo.save_fill(data)

        assert result is not None

    def test_get_fills_for_order(self) -> None:
        """Test getting fills for an order."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_fill1 = self._create_mock_fill(id=1)
        mock_fill2 = self._create_mock_fill(id=2)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_fill1, mock_fill2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        # Lines 152-164: get_fills_for_order
        results = repo.get_fills_for_order(100)

        assert len(results) == 2

    def test_get_fills_for_ticker(self) -> None:
        """Test getting fills for a ticker."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_fill = self._create_mock_fill()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_fill]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        # Lines 184-199: get_fills_for_ticker with time filters
        results = repo.get_fills_for_ticker(
            "TEST-TICKER",
            start_time=start_time,
            end_time=end_time,
            limit=50,
        )

        assert len(results) == 1

    def test_get_fills_for_ticker_no_filters(self) -> None:
        """Test getting fills for a ticker without time filters."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_fill = self._create_mock_fill()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_fill]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        results = repo.get_fills_for_ticker("TEST-TICKER")

        assert len(results) == 1

    def test_get_recent_fills(self) -> None:
        """Test getting recent fills."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_fill1 = self._create_mock_fill(id=1)
        mock_fill2 = self._create_mock_fill(id=2)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_fill1, mock_fill2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        # Lines 217-232: get_recent_fills with filters
        results = repo.get_recent_fills(
            city_code="NYC",
            trading_mode="shadow",
            limit=50,
        )

        assert len(results) == 2

    def test_get_recent_fills_no_filters(self) -> None:
        """Test getting recent fills without filters."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        results = repo.get_recent_fills()

        assert len(results) == 0

    def test_get_public_fills(self) -> None:
        """Test getting public fills with delay."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_fill = self._create_mock_fill()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_fill]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        # Lines 252-269: get_public_fills
        results = repo.get_public_fills(
            city_code="NYC",
            delay_minutes=60,
            limit=50,
        )

        assert len(results) == 1

    def test_get_public_fills_no_filters(self) -> None:
        """Test getting public fills without city filter."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        results = repo.get_public_fills()

        assert len(results) == 0

    def test_get_fills_by_date_range(self) -> None:
        """Test getting fills by date range."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_fill = self._create_mock_fill()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_fill]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2025, 1, 31, tzinfo=timezone.utc)

        # Lines 287-304: get_fills_by_date_range
        results = repo.get_fills_by_date_range(
            start_date=start_date,
            end_date=end_date,
            city_code="NYC",
        )

        assert len(results) == 1

    def test_get_fills_by_date_range_no_city(self) -> None:
        """Test getting fills by date range without city filter."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = FillRepository(mock_db)

        start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2025, 1, 31, tzinfo=timezone.utc)

        results = repo.get_fills_by_date_range(start_date, end_date)

        assert len(results) == 0

    def test_get_fill_stats(self) -> None:
        """Test getting fill statistics."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        # Mock stats result
        mock_row = (100, 5000, 250000.0, 500.0, 10000.0, 45.5)
        mock_session.execute.return_value.one.return_value = mock_row

        repo = FillRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=30)
        end_time = datetime.now(timezone.utc)

        # Lines 322-350: get_fill_stats with all filters
        result = repo.get_fill_stats(
            city_code="NYC",
            start_time=start_time,
            end_time=end_time,
        )

        assert result["total_fills"] == 100
        assert result["total_quantity"] == 5000
        assert result["total_notional"] == 250000.0
        assert result["total_fees"] == 500.0
        assert result["total_pnl"] == 10000.0
        assert result["avg_price"] == 45.5

    def test_get_fill_stats_null_values(self) -> None:
        """Test getting fill statistics with null values."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        # Mock with None values
        mock_row = (0, None, None, None, None, None)
        mock_session.execute.return_value.one.return_value = mock_row

        repo = FillRepository(mock_db)

        result = repo.get_fill_stats()

        assert result["total_fills"] == 0
        assert result["total_quantity"] == 0
        assert result["total_notional"] == 0.0
        assert result["total_fees"] == 0.0
        assert result["total_pnl"] == 0.0
        assert result["avg_price"] == 0.0

    def test_get_pnl_by_city(self) -> None:
        """Test getting P&L by city."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("NYC", 1500.0),
            ("LAX", -200.0),
            ("CHI", None),
        ]

        repo = FillRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=30)
        end_time = datetime.now(timezone.utc)

        # Lines 366-383: get_pnl_by_city with time filters
        result = repo.get_pnl_by_city(start_time=start_time, end_time=end_time)

        assert result["NYC"] == 1500.0
        assert result["LAX"] == -200.0
        assert result["CHI"] == 0.0

    def test_get_pnl_by_city_no_filters(self) -> None:
        """Test getting P&L by city without time filters."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("NYC", 1000.0),
        ]

        repo = FillRepository(mock_db)

        result = repo.get_pnl_by_city()

        assert result["NYC"] == 1000.0

    def test_get_volume_by_city(self) -> None:
        """Test getting volume by city."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("NYC", 5000),
            ("LAX", 3000),
            ("CHI", None),
        ]

        repo = FillRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=30)
        end_time = datetime.now(timezone.utc)

        # Lines 399-416: get_volume_by_city with time filters
        result = repo.get_volume_by_city(start_time=start_time, end_time=end_time)

        assert result["NYC"] == 5000
        assert result["LAX"] == 3000
        assert result["CHI"] == 0

    def test_get_volume_by_city_no_filters(self) -> None:
        """Test getting volume by city without time filters."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("NYC", 1000),
        ]

        repo = FillRepository(mock_db)

        result = repo.get_volume_by_city()

        assert result["NYC"] == 1000

    def test_delete_older_than(self) -> None:
        """Test deleting old fills."""
        from src.shared.db.repositories.fill import FillRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_result = MagicMock()
        mock_result.rowcount = 50
        mock_session.execute.return_value = mock_result

        repo = FillRepository(mock_db)

        # Lines 427-439: delete_older_than
        count = repo.delete_older_than(days=365)

        assert count == 50
