"""Tests for WeatherRepository class."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestWeatherRepository:
    """Tests for WeatherRepository CRUD operations."""

    def _create_mock_db(self) -> MagicMock:
        """Create a mock database manager."""
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)
        return mock_db

    def _create_mock_snapshot(self, **kwargs) -> MagicMock:
        """Create a mock WeatherSnapshot ORM object."""
        defaults = {
            "id": 1,
            "city_code": "NYC",
            "captured_at": datetime.now(timezone.utc),
            "forecast_high": 75,
            "forecast_low": 55,
            "current_temp": 68.5,
            "precipitation_probability": 0.2,
            "forecast_text": "Sunny with clouds",
            "source": "nws",
            "is_stale": False,
            "raw_forecast": {"periods": []},
            "raw_observation": {"temperature": 68.5},
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        mock_snapshot = MagicMock()
        for k, v in defaults.items():
            setattr(mock_snapshot, k, v)
        return mock_snapshot

    def test_init(self) -> None:
        """Test repository initialization."""
        from src.shared.db.repositories.weather import WeatherRepository

        mock_db = self._create_mock_db()
        repo = WeatherRepository(mock_db)

        # Line 90: super().__init__
        assert repo._db is mock_db

    @patch("src.shared.db.repositories.weather.WeatherRepository.save")
    def test_save_snapshot(self, mock_save: MagicMock) -> None:
        """Test saving a new weather snapshot."""
        from src.shared.db.repositories.weather import WeatherRepository, WeatherSnapshotCreate

        mock_db = self._create_mock_db()
        repo = WeatherRepository(mock_db)

        saved_snapshot = self._create_mock_snapshot()
        mock_save.return_value = saved_snapshot

        data = WeatherSnapshotCreate(
            city_code="NYC",
            forecast_high=75,
            forecast_low=55,
            current_temp=68.5,
            precipitation_probability=0.2,
            forecast_text="Sunny with clouds",
            source="nws",
            is_stale=False,
            raw_forecast={"periods": []},
            raw_observation={"temperature": 68.5},
        )

        # Lines 101-123: save_snapshot
        result = repo.save_snapshot(data)

        assert result.city_code == "NYC"
        assert result.forecast_high == 75
        mock_save.assert_called_once()

    def test_get_latest_found(self) -> None:
        """Test get_latest when snapshot exists."""
        from src.shared.db.repositories.weather import WeatherRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_snapshot = self._create_mock_snapshot()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_snapshot

        repo = WeatherRepository(mock_db)

        # Lines 134-145: get_latest found
        result = repo.get_latest("NYC")

        assert result is not None
        assert result.city_code == "NYC"
        mock_session.expunge.assert_called_once_with(mock_snapshot)

    def test_get_latest_not_found(self) -> None:
        """Test get_latest when snapshot doesn't exist."""
        from src.shared.db.repositories.weather import WeatherRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        repo = WeatherRepository(mock_db)

        # Line 146: return None
        result = repo.get_latest("NONEXISTENT")

        assert result is None

    def test_get_history(self) -> None:
        """Test get_history."""
        from src.shared.db.repositories.weather import WeatherRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_snapshot1 = self._create_mock_snapshot(id=1)
        mock_snapshot2 = self._create_mock_snapshot(id=2)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_snapshot1, mock_snapshot2]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = WeatherRepository(mock_db)

        start_time = datetime.now(timezone.utc) - timedelta(days=7)
        end_time = datetime.now(timezone.utc)

        # Lines 166-181: get_history with time filters
        results = repo.get_history(
            "NYC",
            start_time=start_time,
            end_time=end_time,
            limit=50,
        )

        assert len(results) == 2

    def test_get_history_no_time_filters(self) -> None:
        """Test get_history without time filters."""
        from src.shared.db.repositories.weather import WeatherRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = WeatherRepository(mock_db)

        # Lines 169-172: no time filters applied
        results = repo.get_history("NYC")

        assert len(results) == 0

    def test_get_latest_for_all_cities(self) -> None:
        """Test get_latest_for_all_cities."""
        from src.shared.db.repositories.weather import WeatherRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_snapshot_nyc = self._create_mock_snapshot(id=1, city_code="NYC")
        mock_snapshot_lax = self._create_mock_snapshot(id=2, city_code="LAX")
        mock_snapshot_chi = self._create_mock_snapshot(id=3, city_code="CHI")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_snapshot_nyc, mock_snapshot_lax, mock_snapshot_chi]
        mock_session.execute.return_value.scalars.return_value = mock_scalars

        repo = WeatherRepository(mock_db)

        # Lines 190-214: get_latest_for_all_cities
        results = repo.get_latest_for_all_cities()

        assert "NYC" in results
        assert "LAX" in results
        assert "CHI" in results
        assert results["NYC"].city_code == "NYC"
        assert results["LAX"].city_code == "LAX"

    def test_mark_stale(self) -> None:
        """Test mark_stale."""
        from src.shared.db.repositories.weather import WeatherRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        repo = WeatherRepository(mock_db)

        # Lines 225-238: mark_stale
        count = repo.mark_stale("NYC")

        assert count == 5

    def test_delete_older_than(self) -> None:
        """Test deleting old weather snapshots."""
        from src.shared.db.repositories.weather import WeatherRepository

        mock_db = self._create_mock_db()
        mock_session = mock_db.session.return_value.__enter__.return_value

        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_session.execute.return_value = mock_result

        repo = WeatherRepository(mock_db)

        # Lines 249-265: delete_older_than
        count = repo.delete_older_than(days=30)

        assert count == 100
