"""Unit tests for database connection manager."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from src.shared.db.connection import DatabaseManager, get_db


class TestDatabaseManager:
    """Test suite for DatabaseManager."""

    def test_database_manager_initialization(self) -> None:
        """Test DatabaseManager initializes with settings."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")

            assert db_manager.engine == mock_engine
            mock_create_engine.assert_called_once()

    def test_database_manager_uses_settings_url(self) -> None:
        """Test DatabaseManager uses URL from settings when not provided."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine, \
             patch("src.shared.db.connection.get_settings") as mock_get_settings:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            mock_settings = MagicMock()
            mock_settings.database_url = "postgresql://settings:settings@localhost/settings"
            mock_settings.db_pool_size = 5
            mock_settings.db_max_overflow = 10
            mock_settings.db_pool_timeout = 30
            mock_get_settings.return_value = mock_settings

            db_manager = DatabaseManager()

            assert db_manager._database_url == "postgresql://settings:settings@localhost/settings"

    def test_health_check_success(self) -> None:
        """Test health check returns True when database is reachable."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")
            result = db_manager.health_check()

            assert result is True
            mock_conn.execute.assert_called_once()

    def test_health_check_failure(self) -> None:
        """Test health check returns False when database is unreachable."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_engine.connect.side_effect = OperationalError("Connection failed", None, None)
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")
            result = db_manager.health_check()

            assert result is False

    def test_session_context_manager(self) -> None:
        """Test session context manager commits on success."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            with patch("src.shared.db.connection.sessionmaker") as mock_sessionmaker:
                mock_session = MagicMock()
                mock_sessionmaker.return_value = MagicMock(return_value=mock_session)

                db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")

                with db_manager.session() as session:
                    assert session == mock_session

                mock_session.commit.assert_called_once()
                mock_session.close.assert_called_once()

    def test_session_context_manager_rollback_on_error(self) -> None:
        """Test session context manager rolls back on exception."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            with patch("src.shared.db.connection.sessionmaker") as mock_sessionmaker:
                mock_session = MagicMock()
                mock_sessionmaker.return_value = MagicMock(return_value=mock_session)

                db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")

                with pytest.raises(ValueError):
                    with db_manager.session():
                        raise ValueError("Test error")

                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    def test_close_disposes_engine(self) -> None:
        """Test close method disposes of engine."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")
            db_manager.close()

            mock_engine.dispose.assert_called_once()

    def test_engine_property(self) -> None:
        """Test engine property returns the engine."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")

            assert db_manager.engine is mock_engine


class TestWeatherCacheEdgeCases:
    """Tests for weather cache edge cases."""

    def test_weather_cache_invalidate_nonexistent(self) -> None:
        """Test invalidating a city that's not in cache."""
        from src.shared.api.weather_cache import WeatherCache

        with patch("src.shared.api.weather_cache.NWSClient"):
            cache = WeatherCache()
            result = cache.invalidate("NONEXISTENT")

            assert result is False

    def test_weather_cache_invalidate_all_empty(self) -> None:
        """Test invalidating all when cache is empty."""
        from src.shared.api.weather_cache import WeatherCache

        with patch("src.shared.api.weather_cache.NWSClient"):
            cache = WeatherCache()
            count = cache.invalidate_all()

            assert count == 0

    def test_weather_cache_get_stats_empty(self) -> None:
        """Test getting stats from empty cache."""
        from src.shared.api.weather_cache import WeatherCache

        with patch("src.shared.api.weather_cache.NWSClient"):
            cache = WeatherCache()
            stats = cache.get_cache_stats()

            assert stats["total_entries"] == 0
            assert stats["entries"] == {}

    def test_weather_cache_prefetch_with_failures(self) -> None:
        """Test prefetch_all_cities handles failures gracefully."""
        from src.shared.api.weather_cache import WeatherCache

        with patch("src.shared.api.weather_cache.NWSClient") as mock_nws, \
             patch("src.shared.api.weather_cache.city_loader") as mock_loader:

            mock_loader.get_all_cities.return_value = {"NYC": {}, "LAX": {}}
            mock_loader.get_city.side_effect = KeyError("City not found")

            cache = WeatherCache(nws_client=mock_nws.return_value)
            results = cache.prefetch_all_cities()

            # All should fail
            assert all(v is False for v in results.values())

    def test_cached_weather_age_calculation(self) -> None:
        """Test CachedWeather age calculation."""
        from datetime import timedelta
        from src.shared.api.weather_cache import CachedWeather

        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        cached = CachedWeather(
            city_code="NYC",
            forecast={"test": "data"},
            fetched_at=old_time,
        )

        assert cached.age_minutes() >= 10.0
        assert cached.age_seconds() >= 600.0


class TestGetDb:
    """Tests for get_db singleton function."""

    def test_get_db_creates_singleton(self) -> None:
        """Test get_db creates and returns singleton."""
        import src.shared.db.connection as conn_module

        # Reset the global
        original = conn_module._db_manager
        conn_module._db_manager = None

        try:
            with patch.object(conn_module, "DatabaseManager") as mock_class:
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance

                result1 = get_db()
                result2 = get_db()

                # Should only create once
                assert mock_class.call_count == 1
                assert result1 is mock_instance
                assert result2 is mock_instance
        finally:
            # Reset for other tests
            conn_module._db_manager = original

    def test_get_db_returns_existing(self) -> None:
        """Test get_db returns existing instance."""
        import src.shared.db.connection as conn_module

        original = conn_module._db_manager
        mock_existing = MagicMock()
        conn_module._db_manager = mock_existing

        try:
            result = get_db()
            assert result is mock_existing
        finally:
            # Reset for other tests
            conn_module._db_manager = original
