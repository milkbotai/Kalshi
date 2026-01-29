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
        from datetime import datetime, timedelta, timezone
        from src.shared.api.weather_cache import CachedWeather

        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        cached = CachedWeather(
            city_code="NYC",
            forecast={"test": "data"},
            fetched_at=old_time,
        )

        assert cached.age_minutes() >= 10.0
        assert cached.age_seconds() >= 600.0

    def test_weather_cache_get_weather_force_refresh(self) -> None:
        """Test get_weather with force_refresh=True."""
        from src.shared.api.weather_cache import WeatherCache

        with patch("src.shared.api.weather_cache.NWSClient") as mock_nws, \
             patch("src.shared.api.weather_cache.city_loader") as mock_loader:

            mock_city = MagicMock()
            mock_city.code = "NYC"
            mock_city.nws_office = "OKX"
            mock_city.nws_grid_x = 33
            mock_city.nws_grid_y = 37
            mock_city.settlement_station = "KNYC"
            mock_loader.get_city.return_value = mock_city

            mock_nws_instance = MagicMock()
            mock_nws_instance.get_forecast.return_value = {"properties": {"test": "data"}}
            mock_nws_instance.get_latest_observation.return_value = {"properties": {}}

            cache = WeatherCache(nws_client=mock_nws_instance)

            # First call
            result1 = cache.get_weather("NYC")
            assert result1.forecast is not None

            # Second call with force_refresh
            result2 = cache.get_weather("NYC", force_refresh=True)
            assert result2.forecast is not None

            # Should have called API twice
            assert mock_nws_instance.get_forecast.call_count == 2

    def test_weather_cache_fetch_forecast_failure(self) -> None:
        """Test _fetch_and_cache handles forecast failure."""
        from src.shared.api.weather_cache import WeatherCache

        with patch("src.shared.api.weather_cache.NWSClient") as mock_nws, \
             patch("src.shared.api.weather_cache.city_loader") as mock_loader:

            mock_city = MagicMock()
            mock_city.code = "NYC"
            mock_city.nws_office = "OKX"
            mock_city.nws_grid_x = 33
            mock_city.nws_grid_y = 37
            mock_city.settlement_station = "KNYC"
            mock_loader.get_city.return_value = mock_city

            mock_nws_instance = MagicMock()
            mock_nws_instance.get_forecast.side_effect = Exception("Forecast API error")
            mock_nws_instance.get_latest_observation.return_value = {"properties": {"temp": 50}}

            cache = WeatherCache(nws_client=mock_nws_instance)
            result = cache.get_weather("NYC")

            # Should still return result with observation but no forecast
            assert result.forecast is None
            assert result.observation is not None

    def test_weather_cache_fetch_observation_failure(self) -> None:
        """Test _fetch_and_cache handles observation failure."""
        from src.shared.api.weather_cache import WeatherCache

        with patch("src.shared.api.weather_cache.NWSClient") as mock_nws, \
             patch("src.shared.api.weather_cache.city_loader") as mock_loader:

            mock_city = MagicMock()
            mock_city.code = "NYC"
            mock_city.nws_office = "OKX"
            mock_city.nws_grid_x = 33
            mock_city.nws_grid_y = 37
            mock_city.settlement_station = "KNYC"
            mock_loader.get_city.return_value = mock_city

            mock_nws_instance = MagicMock()
            mock_nws_instance.get_forecast.return_value = {"properties": {"test": "data"}}
            mock_nws_instance.get_latest_observation.side_effect = Exception("Observation API error")

            cache = WeatherCache(nws_client=mock_nws_instance)
            result = cache.get_weather("NYC")

            # Should still return result with forecast but no observation
            assert result.forecast is not None
            assert result.observation is None

    def test_weather_cache_stale_data(self) -> None:
        """Test weather cache marks data as stale after threshold."""
        from datetime import datetime, timedelta, timezone
        from src.shared.api.weather_cache import WeatherCache, CachedWeather

        with patch("src.shared.api.weather_cache.NWSClient"):
            cache = WeatherCache(ttl_minutes=30, staleness_threshold_minutes=5)

            # Manually insert stale data
            old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            cache._cache["NYC"] = CachedWeather(
                city_code="NYC",
                forecast={"test": "data"},
                fetched_at=old_time,
            )

            result = cache.get_weather("NYC")

            # Should be marked as stale
            assert result.is_stale is True

    def test_weather_cache_invalidate_existing(self) -> None:
        """Test invalidating an existing cache entry."""
        from datetime import datetime, timezone
        from src.shared.api.weather_cache import WeatherCache, CachedWeather

        with patch("src.shared.api.weather_cache.NWSClient"):
            cache = WeatherCache()

            # Add entry
            cache._cache["NYC"] = CachedWeather(
                city_code="NYC",
                forecast={"test": "data"},
                fetched_at=datetime.now(timezone.utc),
            )

            result = cache.invalidate("NYC")

            assert result is True
            assert "NYC" not in cache._cache

    def test_weather_cache_invalidate_all_with_entries(self) -> None:
        """Test invalidating all entries when cache has data."""
        from datetime import datetime, timezone
        from src.shared.api.weather_cache import WeatherCache, CachedWeather

        with patch("src.shared.api.weather_cache.NWSClient"):
            cache = WeatherCache()

            # Add entries
            cache._cache["NYC"] = CachedWeather(
                city_code="NYC",
                forecast={"test": "data"},
                fetched_at=datetime.now(timezone.utc),
            )
            cache._cache["LAX"] = CachedWeather(
                city_code="LAX",
                forecast={"test": "data"},
                fetched_at=datetime.now(timezone.utc),
            )

            count = cache.invalidate_all()

            assert count == 2
            assert len(cache._cache) == 0


class TestWeatherCacheAdvanced:
    """Advanced tests for weather cache edge cases."""

    def test_weather_cache_concurrent_access(self) -> None:
        """Test weather cache handles concurrent access."""
        import threading
        from src.shared.api.weather_cache import WeatherCache

        with patch("src.shared.api.weather_cache.NWSClient") as mock_nws, \
             patch("src.shared.api.weather_cache.city_loader") as mock_loader:

            mock_city = MagicMock()
            mock_city.code = "NYC"
            mock_city.nws_office = "OKX"
            mock_city.nws_grid_x = 33
            mock_city.nws_grid_y = 37
            mock_city.settlement_station = "KNYC"
            mock_loader.get_city.return_value = mock_city

            mock_nws_instance = MagicMock()
            mock_nws_instance.get_forecast.return_value = {"properties": {"test": "data"}}
            mock_nws_instance.get_latest_observation.return_value = {"properties": {}}

            cache = WeatherCache(nws_client=mock_nws_instance)

            results = []

            def fetch_weather():
                result = cache.get_weather("NYC")
                results.append(result)

            threads = [threading.Thread(target=fetch_weather) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(results) == 5
            assert all(r.city_code == "NYC" for r in results)

    def test_weather_cache_ttl_boundary(self) -> None:
        """Test weather cache at exact TTL boundary."""
        from datetime import datetime, timedelta, timezone
        from src.shared.api.weather_cache import WeatherCache, CachedWeather

        with patch("src.shared.api.weather_cache.NWSClient"):
            cache = WeatherCache(ttl_minutes=5)

            # Insert data exactly at TTL boundary
            boundary_time = datetime.now(timezone.utc) - timedelta(minutes=5)
            cache._cache["NYC"] = CachedWeather(
                city_code="NYC",
                forecast={"test": "data"},
                fetched_at=boundary_time,
            )

            # Should be expired (>= TTL)
            with patch.object(cache, "_fetch_and_cache") as mock_fetch:
                mock_fetch.return_value = CachedWeather(
                    city_code="NYC",
                    forecast={"new": "data"},
                )
                result = cache.get_weather("NYC")

                # Should have fetched new data
                mock_fetch.assert_called_once()

    def test_weather_cache_get_stats_with_mixed_entries(self) -> None:
        """Test get_cache_stats with mix of fresh and stale entries."""
        from datetime import datetime, timedelta, timezone
        from src.shared.api.weather_cache import WeatherCache, CachedWeather

        with patch("src.shared.api.weather_cache.NWSClient"):
            cache = WeatherCache(ttl_minutes=30, staleness_threshold_minutes=5)

            # Fresh entry
            cache._cache["NYC"] = CachedWeather(
                city_code="NYC",
                forecast={"test": "data"},
                fetched_at=datetime.now(timezone.utc),
            )

            # Stale entry
            cache._cache["LAX"] = CachedWeather(
                city_code="LAX",
                forecast={"test": "data"},
                fetched_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            )

            stats = cache.get_cache_stats()

            assert stats["total_entries"] == 2
            assert stats["entries"]["NYC"]["is_stale"] is False
            assert stats["entries"]["LAX"]["is_stale"] is True


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


class TestResponseModels:
    """Tests for response model edge cases."""

    def test_market_spread_with_none_values(self) -> None:
        """Test Market spread_cents with None bid/ask."""
        from src.shared.api.response_models import Market

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=None,
            yes_ask=None,
        )

        assert market.spread_cents is None
        assert market.mid_price is None

    def test_market_spread_calculation(self) -> None:
        """Test Market spread_cents calculation."""
        from src.shared.api.response_models import Market

        market = Market(
            ticker="TEST",
            event_ticker="TEST",
            title="Test",
            status="open",
            yes_bid=45,
            yes_ask=48,
        )

        assert market.spread_cents == 3
        assert market.mid_price == 46.5

    def test_orderbook_best_prices_empty(self) -> None:
        """Test Orderbook best prices with empty levels."""
        from src.shared.api.response_models import Orderbook

        orderbook = Orderbook(yes=[], no=[])

        assert orderbook.best_yes_bid is None
        assert orderbook.best_yes_ask is None

    def test_order_is_filled_property(self) -> None:
        """Test Order is_filled property."""
        from src.shared.api.response_models import Order
        from datetime import datetime, timezone

        order = Order(
            order_id="123",
            ticker="TEST",
            side="yes",
            action="buy",
            count=10,
            status="filled",
            created_time=datetime.now(timezone.utc),
            filled_count=10,
        )

        assert order.is_filled is True

    def test_position_average_price_zero_position(self) -> None:
        """Test Position average_price with zero position."""
        from src.shared.api.response_models import Position

        position = Position(
            ticker="TEST",
            position=0,
            total_cost=0,
        )

        assert position.average_price is None

    def test_fill_price_and_notional(self) -> None:
        """Test Fill price and notional_value properties."""
        from src.shared.api.response_models import Fill
        from datetime import datetime, timezone

        fill = Fill(
            fill_id="123",
            order_id="456",
            ticker="TEST",
            side="yes",
            action="buy",
            count=10,
            yes_price=50,
            created_time=datetime.now(timezone.utc),
        )

        assert fill.price == 50
        assert fill.notional_value == 500

    def test_balance_available_balance(self) -> None:
        """Test Balance available_balance property."""
        from src.shared.api.response_models import Balance

        balance = Balance(
            balance=10000,
            payout=2000,
        )

        assert balance.available_balance == 8000

    def test_observation_extract_value_from_dict(self) -> None:
        """Test Observation extracts value from NWS dict format."""
        from src.shared.api.response_models import Observation
        from datetime import datetime, timezone

        # NWS returns values as {"value": 20.5, "unitCode": "wmoUnit:degC"}
        obs = Observation(
            timestamp=datetime.now(timezone.utc),
            temperature={"value": 20.5, "unitCode": "wmoUnit:degC"},
        )

        assert obs.temperature == 20.5

    def test_observation_extract_value_none(self) -> None:
        """Test Observation handles None values."""
        from src.shared.api.response_models import Observation
        from datetime import datetime, timezone

        obs = Observation(
            timestamp=datetime.now(timezone.utc),
            temperature=None,
        )

        assert obs.temperature is None
