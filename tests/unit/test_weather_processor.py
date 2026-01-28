"""Unit tests for weather data processor."""

from datetime import datetime, timezone

import pytest

from src.analytics.weather_processor import WeatherProcessor
from src.shared.api.response_models import Forecast, ForecastPeriod, Observation


class TestWeatherProcessor:
    """Test suite for WeatherProcessor."""

    @pytest.fixture
    def processor(self) -> WeatherProcessor:
        """Create weather processor instance."""
        return WeatherProcessor()

    @pytest.fixture
    def sample_forecast_period(self) -> ForecastPeriod:
        """Create sample forecast period."""
        return ForecastPeriod(
            number=1,
            name="Tonight",
            start_time=datetime(2026, 1, 25, 18, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 26, 6, 0, tzinfo=timezone.utc),
            is_daytime=False,
            temperature=32,
            temperature_unit="F",
            wind_speed="5 mph",
            wind_direction="NW",
            short_forecast="Clear",
            detailed_forecast="Clear skies. Chance of rain 20%.",
        )

    @pytest.fixture
    def sample_forecast(self, sample_forecast_period: ForecastPeriod) -> Forecast:
        """Create sample forecast."""
        now = datetime.now(timezone.utc)
        return Forecast(
            updated=now,
            units="us",
            forecast_generator="BaselineForecast",
            generated_at=now,
            update_time=now,
            periods=[sample_forecast_period],
        )

    @pytest.fixture
    def sample_observation(self) -> Observation:
        """Create sample observation."""
        return Observation(
            timestamp=datetime.now(timezone.utc),
            text_description="Partly Cloudy",
            temperature=20.5,  # Celsius
            dewpoint=15.0,  # Celsius
            wind_direction=180,
            wind_speed=10.5,
            relative_humidity=65.0,
        )

    def test_processor_initialization(self, processor: WeatherProcessor) -> None:
        """Test WeatherProcessor initializes correctly."""
        assert processor is not None

    def test_parse_forecast(self, processor: WeatherProcessor, sample_forecast: Forecast) -> None:
        """Test parsing forecast into normalized dictionary."""
        result = processor.parse_forecast(sample_forecast)

        assert "updated" in result
        assert "generated_at" in result
        assert "periods" in result
        assert len(result["periods"]) == 1

        period = result["periods"][0]
        assert period["number"] == 1
        assert period["name"] == "Tonight"
        assert period["temperature"] == 32
        assert period["is_daytime"] is False

    def test_parse_forecast_extracts_precipitation(
        self, processor: WeatherProcessor, sample_forecast: Forecast
    ) -> None:
        """Test forecast parsing extracts precipitation probability."""
        result = processor.parse_forecast(sample_forecast)

        period = result["periods"][0]
        assert "precipitation_probability" in period
        assert period["precipitation_probability"] == 0.20

    def test_parse_observation(
        self, processor: WeatherProcessor, sample_observation: Observation
    ) -> None:
        """Test parsing observation into normalized dictionary."""
        result = processor.parse_observation(sample_observation)

        assert "timestamp" in result
        assert "temperature_f" in result
        assert "dewpoint_f" in result
        assert "wind_direction" in result
        assert "relative_humidity" in result

    def test_parse_observation_converts_celsius_to_fahrenheit(
        self, processor: WeatherProcessor, sample_observation: Observation
    ) -> None:
        """Test observation parsing converts Celsius to Fahrenheit."""
        result = processor.parse_observation(sample_observation)

        # 20.5°C should be approximately 68.9°F
        assert result["temperature_f"] is not None
        assert 68.0 <= result["temperature_f"] <= 69.0

    def test_parse_observation_handles_null_temperature(self, processor: WeatherProcessor) -> None:
        """Test observation parsing handles null temperature."""
        obs = Observation(
            timestamp=datetime.now(timezone.utc),
            temperature=None,
            dewpoint=None,
        )

        result = processor.parse_observation(obs)

        assert result["temperature_f"] is None
        assert result["dewpoint_f"] is None

    def test_normalize_temperature(self, processor: WeatherProcessor) -> None:
        """Test temperature normalization."""
        result = processor.normalize_temperature(temp=72.0, city="NYC")

        # Currently returns raw temperature (placeholder)
        assert result == 72.0

    def test_calculate_temp_anomaly(self, processor: WeatherProcessor) -> None:
        """Test temperature anomaly calculation."""
        anomaly = processor.calculate_temp_anomaly(current=75.0, historical_avg=65.0)

        assert anomaly == 10.0

    def test_calculate_temp_anomaly_negative(self, processor: WeatherProcessor) -> None:
        """Test temperature anomaly calculation with negative anomaly."""
        anomaly = processor.calculate_temp_anomaly(current=55.0, historical_avg=65.0)

        assert anomaly == -10.0

    def test_extract_precipitation_probability_percentage(
        self, processor: WeatherProcessor
    ) -> None:
        """Test extracting precipitation probability from percentage."""
        test_cases = [
            ("Chance of rain 40%", 0.40),
            ("Rain 75%", 0.75),
            ("10% chance of snow", 0.10),
        ]

        for text, expected in test_cases:
            result = processor.extract_precipitation_probability(text)
            assert result == expected, f"Failed for: {text}"

    def test_extract_precipitation_probability_percent_word(
        self, processor: WeatherProcessor
    ) -> None:
        """Test extracting precipitation probability from 'percent' word."""
        text = "Chance of rain 40 percent"
        result = processor.extract_precipitation_probability(text)

        assert result == 0.40

    def test_extract_precipitation_probability_qualitative(
        self, processor: WeatherProcessor
    ) -> None:
        """Test extracting precipitation probability from qualitative terms."""
        test_cases = [
            ("Rain likely", 0.70),
            ("Possible showers", 0.40),
            ("Slight chance of rain", 0.20),
        ]

        for text, expected in test_cases:
            result = processor.extract_precipitation_probability(text)
            assert result == expected, f"Failed for: {text}"

    def test_extract_precipitation_probability_none(self, processor: WeatherProcessor) -> None:
        """Test extracting precipitation probability when none mentioned."""
        text = "Clear skies with sunshine"
        result = processor.extract_precipitation_probability(text)

        assert result == 0.0

    def test_extract_precipitation_probability_empty_string(
        self, processor: WeatherProcessor
    ) -> None:
        """Test extracting precipitation probability from empty string."""
        result = processor.extract_precipitation_probability("")

        assert result == 0.0

    def test_celsius_to_fahrenheit_conversion(self) -> None:
        """Test Celsius to Fahrenheit conversion."""
        test_cases = [
            (0.0, 32.0),
            (100.0, 212.0),
            (20.0, 68.0),
            (-40.0, -40.0),
        ]

        for celsius, expected_f in test_cases:
            result = WeatherProcessor._celsius_to_fahrenheit(celsius)
            assert abs(result - expected_f) < 0.1, f"Failed for {celsius}°C"
