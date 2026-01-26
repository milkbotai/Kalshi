"""Analytics module for weather processing and signal generation."""

from src.analytics.opportunity_detector import OpportunityDetector
from src.analytics.signal_generator import Signal, SignalGenerator
from src.analytics.weather_processor import WeatherProcessor

__all__ = [
    "WeatherProcessor",
    "OpportunityDetector",
    "SignalGenerator",
    "Signal",
]
