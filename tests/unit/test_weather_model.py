"""Unit tests for WeatherSnapshot model."""

from datetime import timedelta

from src.shared.models import WeatherSnapshot, utcnow


class TestWeatherSnapshotModel:
    """Test suite for WeatherSnapshot model."""

    def test_weather_snapshot_creation(self) -> None:
        """Test creating a WeatherSnapshot instance."""
        snapshot = WeatherSnapshot(
            city_code="NYC",
            captured_at=utcnow(),
            nws_forecast={"periods": [{"temperature": 72}]},
            nws_observation={"temperature": 70},
            data_quality_flags={"fresh": True},
        )

        assert snapshot.city_code == "NYC"
        assert snapshot.has_forecast is True
        assert snapshot.is_stale is False

    def test_weather_snapshot_is_stale(self) -> None:
        """Test stale detection for old weather data."""
        old_time = utcnow() - timedelta(minutes=20)
        snapshot = WeatherSnapshot(
            city_code="NYC",
            captured_at=old_time,
            nws_forecast={"periods": []},
        )

        assert snapshot.is_stale is True

    def test_weather_snapshot_has_forecast_false(self) -> None:
        """Test has_forecast returns False when no forecast data."""
        snapshot = WeatherSnapshot(
            city_code="NYC",
            captured_at=utcnow(),
            nws_forecast=None,
        )

        assert snapshot.has_forecast is False

    def test_weather_snapshot_repr(self) -> None:
        """Test WeatherSnapshot string representation."""
        now = utcnow()
        snapshot = WeatherSnapshot(
            city_code="NYC",
            captured_at=now,
        )

        repr_str = repr(snapshot)
        assert "NYC" in repr_str
        assert "WeatherSnapshot" in repr_str
