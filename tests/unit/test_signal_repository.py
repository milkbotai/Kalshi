"""Tests for SignalRepository class."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestSignalRepository:
    """Tests for SignalRepository CRUD operations."""

    def _create_mock_db(self) -> MagicMock:
        """Create a mock database manager."""
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)
        return mock_db

    def _create_mock_signal(self, **kwargs) -> MagicMock:
        """Create a mock Signal ORM object."""
        defaults = {
            "id": 1,
            "ticker": "TEST-TICKER",
            "city_code": "NYC",
            "strategy_name": "daily_high_temp",
            "side": "yes",
            "decision": "BUY",
            "p_yes": 0.65,
            "uncertainty": 0.05,
            "edge": 5.0,
            "confidence": 0.8,
            "max_price": 70.0,
            "reason": "Strong signal",
            "features": {"temp_diff": 5.0},
            "weather_snapshot_id": 100,
            "market_snapshot_id": 200,
            "trading_mode": "shadow",
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        mock_signal = MagicMock()
        for k, v in defaults.items():
            setattr(mock_signal, k, v)
        return mock_signal

    def test_init(self) -> None:
        """Test repository initialization."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        repo = SignalRepository(mock_db)

        # Line 102: super().__init__
        assert repo._db is mock_db

    @patch("src.shared.db.repositories.signal.SignalRepository.save")
    def test_save_signal(self, mock_save: MagicMock) -> None:
        """Test saving a new signal."""
        from src.shared.db.repositories.signal import SignalRepository, SignalCreate

        mock_db = self._create_mock_db()
        repo = SignalRepository(mock_db)

        saved_signal = self._create_mock_signal()
        mock_save.return_value = saved_signal

        data = SignalCreate(
            ticker="TEST-TICKER",
            city_code="NYC",
            strategy_name="daily_high_temp",
            side="yes",
            decision="BUY",
            p_yes=0.65,
            uncertainty=0.05,
            edge=5.0,
            confidence=0.8,
            max_price=70.0,
            reason="Strong signal",
            features={"temp_diff": 5.0},
            weather_snapshot_id=100,
            market_snapshot_id=200,
            trading_mode="shadow",
        )

        # Lines 113-141: save_signal
        result = repo.save_signal(data)

        assert result.ticker == "TEST-TICKER"
        assert result.decision == "BUY"
        mock_save.assert_called_once()

    def test_get_recent_signals(self) -> None:
        """Test getting recent signals."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_signal1 = self._create_mock_signal(id=1)
        mock_signal2 = self._create_mock_signal(id=2)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_signal1, mock_signal2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = SignalRepository(mock_db)

        # Lines 161-178: get_recent_signals with all filters
        results = repo.get_recent_signals(
            city_code="NYC",
            strategy_name="daily_high_temp",
            decision="BUY",
            limit=50,
        )

        assert len(results) == 2

    def test_get_recent_signals_no_filters(self) -> None:
        """Test getting recent signals without filters."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = SignalRepository(mock_db)

        results = repo.get_recent_signals()

        assert len(results) == 0

    def test_get_signals_for_ticker(self) -> None:
        """Test getting signals for a ticker."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_signal = self._create_mock_signal()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_signal]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = SignalRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        # Lines 198-213: get_signals_for_ticker with time filters
        results = repo.get_signals_for_ticker(
            "TEST-TICKER",
            start_time=start_time,
            end_time=end_time,
            limit=50,
        )

        assert len(results) == 1

    def test_get_signals_for_ticker_no_filters(self) -> None:
        """Test getting signals for a ticker without time filters."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = SignalRepository(mock_db)

        results = repo.get_signals_for_ticker("TEST-TICKER")

        assert len(results) == 0

    def test_get_actionable_signals(self) -> None:
        """Test getting actionable signals."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_signal = self._create_mock_signal(decision="BUY", edge=5.0)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_signal]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = SignalRepository(mock_db)

        # Lines 231-248: get_actionable_signals with filters
        results = repo.get_actionable_signals(
            city_code="NYC",
            min_edge=3.0,
            limit=50,
        )

        assert len(results) == 1

    def test_get_actionable_signals_no_city(self) -> None:
        """Test getting actionable signals without city filter."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = SignalRepository(mock_db)

        results = repo.get_actionable_signals()

        assert len(results) == 0

    def test_get_signals_by_strategy(self) -> None:
        """Test getting signals by strategy."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_signal1 = self._create_mock_signal(id=1)
        mock_signal2 = self._create_mock_signal(id=2)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_signal1, mock_signal2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = SignalRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=7)
        end_time = datetime.now(timezone.utc)

        # Lines 266-281: get_signals_by_strategy with time filters
        results = repo.get_signals_by_strategy(
            "daily_high_temp",
            start_time=start_time,
            end_time=end_time,
        )

        assert len(results) == 2

    def test_get_signals_by_strategy_no_time_filters(self) -> None:
        """Test getting signals by strategy without time filters."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = SignalRepository(mock_db)

        results = repo.get_signals_by_strategy("daily_high_temp")

        assert len(results) == 0

    def test_count_by_decision(self) -> None:
        """Test counting signals by decision."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("BUY", 50),
            ("SELL", 30),
            ("HOLD", 20),
        ]

        repo = SignalRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=30)
        end_time = datetime.now(timezone.utc)

        # Lines 299-315: count_by_decision with all filters
        result = repo.count_by_decision(
            city_code="NYC",
            start_time=start_time,
            end_time=end_time,
        )

        assert result["BUY"] == 50
        assert result["SELL"] == 30
        assert result["HOLD"] == 20

    def test_count_by_decision_no_filters(self) -> None:
        """Test counting signals by decision without filters."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = []

        repo = SignalRepository(mock_db)

        result = repo.count_by_decision()

        assert result == {}

    def test_get_average_edge_by_strategy(self) -> None:
        """Test getting average edge by strategy."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("daily_high_temp", 5.5),
            ("mean_reversion", 3.2),
            ("momentum", None),
        ]

        repo = SignalRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=30)
        end_time = datetime.now(timezone.utc)

        # Lines 331-348: get_average_edge_by_strategy with time filters
        result = repo.get_average_edge_by_strategy(
            start_time=start_time,
            end_time=end_time,
        )

        assert result["daily_high_temp"] == 5.5
        assert result["mean_reversion"] == 3.2
        assert result["momentum"] == 0.0

    def test_get_average_edge_by_strategy_no_filters(self) -> None:
        """Test getting average edge by strategy without filters."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_session.execute.return_value.all.return_value = [
            ("daily_high_temp", 4.0),
        ]

        repo = SignalRepository(mock_db)

        result = repo.get_average_edge_by_strategy()

        assert result["daily_high_temp"] == 4.0

    def test_delete_older_than(self) -> None:
        """Test deleting old signals."""
        from src.shared.db.repositories.signal import SignalRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_session.execute.return_value = mock_result

        repo = SignalRepository(mock_db)

        # Lines 359-371: delete_older_than
        count = repo.delete_older_than(days=90)

        assert count == 100
