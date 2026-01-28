"""Weather data processor for analytics and trading signals.

Processes NWS forecast and observation data into normalized formats
suitable for strategy evaluation and signal generation.
"""

import re
from typing import Any

from src.shared.api.response_models import Forecast, ForecastPeriod, Observation
from src.shared.config.logging import get_logger

logger = get_logger(__name__)


class WeatherProcessor:
    """Processes weather data from NWS into normalized formats.

    Handles temperature conversions, anomaly calculations, and
    precipitation probability extraction.
    """

    def __init__(self) -> None:
        """Initialize weather processor."""
        logger.info("weather_processor_initialized")

    def parse_forecast(self, forecast: Forecast) -> dict[str, Any]:
        """Parse NWS forecast into normalized dictionary.

        Args:
            forecast: Forecast response model from NWS

        Returns:
            Dictionary with normalized forecast data

        Example:
            >>> processor = WeatherProcessor()
            >>> data = processor.parse_forecast(forecast)
            >>> high_temp = data["periods"][0]["temperature"]
        """
        logger.debug("parsing_forecast", num_periods=len(forecast.periods))

        periods_data = []
        for period in forecast.periods:
            period_dict = {
                "number": period.number,
                "name": period.name,
                "start_time": period.start_time,
                "end_time": period.end_time,
                "is_daytime": period.is_daytime,
                "temperature": period.temperature,
                "temperature_unit": period.temperature_unit,
                "wind_speed": period.wind_speed,
                "wind_direction": period.wind_direction,
                "short_forecast": period.short_forecast,
                "detailed_forecast": period.detailed_forecast,
                "precipitation_probability": self.extract_precipitation_probability(
                    period.detailed_forecast
                ),
            }
            periods_data.append(period_dict)

        return {
            "updated": forecast.updated,
            "generated_at": forecast.generated_at,
            "periods": periods_data,
        }

    def parse_observation(self, observation: Observation) -> dict[str, Any]:
        """Parse NWS observation into normalized dictionary.

        Args:
            observation: Observation response model from NWS

        Returns:
            Dictionary with normalized observation data
        """
        logger.debug("parsing_observation", timestamp=observation.timestamp)

        # Convert Celsius to Fahrenheit for consistency
        temp_f = None
        if observation.temperature is not None:
            temp_f = self._celsius_to_fahrenheit(observation.temperature)

        dewpoint_f = None
        if observation.dewpoint is not None:
            dewpoint_f = self._celsius_to_fahrenheit(observation.dewpoint)

        return {
            "timestamp": observation.timestamp,
            "temperature_f": temp_f,
            "dewpoint_f": dewpoint_f,
            "wind_direction": observation.wind_direction,
            "wind_speed": observation.wind_speed,
            "relative_humidity": observation.relative_humidity,
            "text_description": observation.text_description,
        }

    def normalize_temperature(self, temp: float, city: str) -> float:
        """Normalize temperature relative to city baseline.

        Args:
            temp: Temperature in Fahrenheit
            city: City code

        Returns:
            Normalized temperature (z-score placeholder)

        Note:
            Currently returns raw temperature. Will be enhanced with
            historical baselines in future stories.
        """
        logger.debug("normalizing_temperature", temp=temp, city=city)

        # Placeholder: return raw temperature
        # TODO: Implement z-score normalization with historical data
        return temp

    def calculate_temp_anomaly(self, current: float, historical_avg: float) -> float:
        """Calculate temperature anomaly from historical average.

        Args:
            current: Current temperature in Fahrenheit
            historical_avg: Historical average temperature

        Returns:
            Temperature anomaly (current - historical)
        """
        anomaly = current - historical_avg

        logger.debug(
            "temperature_anomaly_calculated",
            current=current,
            historical_avg=historical_avg,
            anomaly=anomaly,
        )

        return anomaly

    def extract_precipitation_probability(self, forecast_text: str) -> float:
        """Extract precipitation probability from forecast text.

        Args:
            forecast_text: Detailed forecast text from NWS

        Returns:
            Precipitation probability from 0.0 to 1.0

        Example:
            >>> processor = WeatherProcessor()
            >>> prob = processor.extract_precipitation_probability(
            ...     "Chance of rain 40%"
            ... )
            >>> assert prob == 0.40
        """
        if not forecast_text:
            return 0.0

        # Look for percentage patterns like "40%", "40 percent", etc.
        patterns = [
            r"(\d+)%",  # "40%"
            r"(\d+)\s*percent",  # "40 percent"
            r"chance.*?(\d+)",  # "chance of rain 40"
        ]

        for pattern in patterns:
            match = re.search(pattern, forecast_text, re.IGNORECASE)
            if match:
                probability = float(match.group(1)) / 100.0
                logger.debug(
                    "precipitation_probability_extracted",
                    text=forecast_text[:50],
                    probability=probability,
                )
                return probability

        # Check for qualitative terms (order matters - check "slight" before "chance")
        text_lower = forecast_text.lower()
        if "likely" in text_lower or "probable" in text_lower:
            return 0.70
        elif "slight" in text_lower:
            return 0.20
        elif "chance" in text_lower or "possible" in text_lower:
            return 0.40

        return 0.0

    @staticmethod
    def _celsius_to_fahrenheit(celsius: float) -> float:
        """Convert Celsius to Fahrenheit.

        Args:
            celsius: Temperature in Celsius

        Returns:
            Temperature in Fahrenheit
        """
        return (celsius * 9.0 / 5.0) + 32.0
