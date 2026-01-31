"""Tests for MarketRepository class."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestMarketSnapshotModel:
    """Tests for MarketSnapshotModel pydantic model."""

    def test_spread_cents_property(self) -> None:
        """Test spread_cents property calculation."""
        from src.shared.db.repositories.market import MarketSnapshotModel

        model = MarketSnapshotModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            captured_at=datetime.now(timezone.utc),
            yes_bid=45,
            yes_ask=48,
            created_at=datetime.now(timezone.utc),
        )

        # Lines 55-56: spread_cents
        assert model.spread_cents == 3

    def test_spread_cents_property_none(self) -> None:
        """Test spread_cents returns None when bid/ask missing."""
        from src.shared.db.repositories.market import MarketSnapshotModel

        model = MarketSnapshotModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            captured_at=datetime.now(timezone.utc),
            yes_bid=None,
            yes_ask=48,
            created_at=datetime.now(timezone.utc),
        )

        # Line 57: return None
        assert model.spread_cents is None

    def test_mid_price_property(self) -> None:
        """Test mid_price property calculation."""
        from src.shared.db.repositories.market import MarketSnapshotModel

        model = MarketSnapshotModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            captured_at=datetime.now(timezone.utc),
            yes_bid=45,
            yes_ask=48,
            created_at=datetime.now(timezone.utc),
        )

        # Lines 62-63: mid_price
        assert model.mid_price == 46.5

    def test_mid_price_property_none(self) -> None:
        """Test mid_price returns None when bid/ask missing."""
        from src.shared.db.repositories.market import MarketSnapshotModel

        model = MarketSnapshotModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            captured_at=datetime.now(timezone.utc),
            yes_bid=45,
            yes_ask=None,
            created_at=datetime.now(timezone.utc),
        )

        # Line 64: return None
        assert model.mid_price is None


class TestMarketRepository:
    """Tests for MarketRepository CRUD operations."""

    def _create_mock_db(self) -> MagicMock:
        """Create a mock database manager."""
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)
        return mock_db

    def _create_mock_snapshot(self, **kwargs) -> MagicMock:
        """Create a mock MarketSnapshot ORM object."""
        defaults = {
            "id": 1,
            "ticker": "TEST-TICKER",
            "city_code": "NYC",
            "event_ticker": "EVENT-123",
            "captured_at": datetime.now(timezone.utc),
            "yes_bid": 45,
            "yes_ask": 48,
            "no_bid": 52,
            "no_ask": 55,
            "last_price": 46,
            "volume": 1000,
            "open_interest": 500,
            "status": "open",
            "strike_price": 40.0,
            "close_time": None,
            "expiration_time": None,
            "raw_payload": {"key": "value"},
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        mock_snapshot = MagicMock()
        for k, v in defaults.items():
            setattr(mock_snapshot, k, v)
        return mock_snapshot

    def test_init(self) -> None:
        """Test repository initialization."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        repo = MarketRepository(mock_db)

        # Line 115: super().__init__
        assert repo._db is mock_db

    @patch("src.shared.db.repositories.market.MarketRepository.save")
    def test_save_snapshot(self, mock_save: MagicMock) -> None:
        """Test saving a new market snapshot."""
        from src.shared.db.repositories.market import MarketRepository, MarketSnapshotCreate

        mock_db = self._create_mock_db()
        repo = MarketRepository(mock_db)

        saved_snapshot = self._create_mock_snapshot()
        mock_save.return_value = saved_snapshot

        data = MarketSnapshotCreate(
            ticker="TEST-TICKER",
            city_code="NYC",
            event_ticker="EVENT-123",
            yes_bid=45,
            yes_ask=48,
            no_bid=52,
            no_ask=55,
            last_price=46,
            volume=1000,
            open_interest=500,
            status="open",
            strike_price=40.0,
            raw_payload={"key": "value"},
        )

        # Lines 126-154: save_snapshot
        result = repo.save_snapshot(data)

        assert result.ticker == "TEST-TICKER"
        mock_save.assert_called_once()

    def test_get_latest_found(self) -> None:
        """Test get_latest when snapshot exists."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_snapshot = self._create_mock_snapshot()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_snapshot

        repo = MarketRepository(mock_db)

        # Lines 165-177: get_latest
        result = repo.get_latest("TEST-TICKER")

        assert result is not None
        assert result.ticker == "TEST-TICKER"
        mock_session.expunge.assert_called_once_with(mock_snapshot)

    def test_get_latest_not_found(self) -> None:
        """Test get_latest when snapshot doesn't exist."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        repo = MarketRepository(mock_db)

        result = repo.get_latest("NONEXISTENT")

        assert result is None

    def test_get_active_markets(self) -> None:
        """Test get_active_markets."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_snapshot1 = self._create_mock_snapshot(id=1, status="open")
        mock_snapshot2 = self._create_mock_snapshot(id=2, status="open")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_snapshot1, mock_snapshot2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = MarketRepository(mock_db)

        # Lines 188-218: get_active_markets
        results = repo.get_active_markets("NYC")

        assert len(results) == 2

    def test_get_markets_by_status(self) -> None:
        """Test get_markets_by_status."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_snapshot = self._create_mock_snapshot(status="closed")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_snapshot]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = MarketRepository(mock_db)

        # Lines 232-262: get_markets_by_status with city filter
        results = repo.get_markets_by_status("closed", city_code="NYC")

        assert len(results) == 1

    def test_get_markets_by_status_no_city(self) -> None:
        """Test get_markets_by_status without city filter."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = MarketRepository(mock_db)

        # Lines 241-244: no city_code filter applied
        results = repo.get_markets_by_status("open")

        assert len(results) == 0

    def test_get_history(self) -> None:
        """Test get_history."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_snapshot1 = self._create_mock_snapshot(id=1)
        mock_snapshot2 = self._create_mock_snapshot(id=2)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_snapshot1, mock_snapshot2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = MarketRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=7)
        end_time = datetime.now(timezone.utc)

        # Lines 282-297: get_history with time filters
        results = repo.get_history(
            "TEST-TICKER",
            start_time=start_time,
            end_time=end_time,
            limit=50,
        )

        assert len(results) == 2

    def test_get_history_no_time_filters(self) -> None:
        """Test get_history without time filters."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = MarketRepository(mock_db)

        results = repo.get_history("TEST-TICKER")

        assert len(results) == 0

    def test_get_by_strike_range(self) -> None:
        """Test get_by_strike_range."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_snapshot1 = self._create_mock_snapshot(id=1, strike_price=35.0)
        mock_snapshot2 = self._create_mock_snapshot(id=2, strike_price=40.0)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_snapshot1, mock_snapshot2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = MarketRepository(mock_db)

        # Lines 317-348: get_by_strike_range
        results = repo.get_by_strike_range(
            city_code="NYC",
            min_strike=30.0,
            max_strike=45.0,
            status="open",
        )

        assert len(results) == 2

    def test_delete_older_than(self) -> None:
        """Test deleting old market snapshots."""
        from src.shared.db.repositories.market import MarketRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_result = MagicMock()
        mock_result.rowcount = 75
        mock_session.execute.return_value = mock_result

        repo = MarketRepository(mock_db)

        # Lines 359-375: delete_older_than
        count = repo.delete_older_than(days=30)

        assert count == 75
