"""Analytics module for weather processing, signal generation, and rollups."""

from src.analytics.api import AnalyticsAPI, APIResponse, create_analytics_api
from src.analytics.health import (
    ComponentHealth,
    ComponentStatus,
    SystemHealth,
    check_degraded_components,
    get_current_health,
    record_health_check,
)
from src.analytics.opportunity_detector import OpportunityDetector
from src.analytics.rollups import (
    CityMetrics,
    EquityCurvePoint,
    StrategyMetrics,
    create_rollup_tables,
    get_city_metrics,
    get_equity_curve,
    get_strategy_metrics,
    run_daily_rollups,
    update_city_metrics,
    update_equity_curve,
    update_strategy_metrics,
)
from src.analytics.signal_generator import Signal, SignalGenerator
from src.analytics.weather_processor import WeatherProcessor

__all__ = [
    # Weather processing
    "WeatherProcessor",
    "OpportunityDetector",
    "SignalGenerator",
    "Signal",
    # Rollups
    "CityMetrics",
    "StrategyMetrics",
    "EquityCurvePoint",
    "create_rollup_tables",
    "update_city_metrics",
    "update_strategy_metrics",
    "update_equity_curve",
    "get_city_metrics",
    "get_strategy_metrics",
    "get_equity_curve",
    "run_daily_rollups",
    # Health
    "ComponentStatus",
    "ComponentHealth",
    "SystemHealth",
    "record_health_check",
    "get_current_health",
    "check_degraded_components",
    # API
    "AnalyticsAPI",
    "APIResponse",
    "create_analytics_api",
]
