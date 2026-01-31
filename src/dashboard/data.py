"""Data provider for dashboard.

Provides data access layer for the Streamlit dashboard,
connecting to the analytics API and NWS weather data.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from src.shared.config.cities import city_loader
from src.shared.config.logging import get_logger

logger = get_logger(__name__)

# NWS API settings
NWS_USER_AGENT = "Milkbot/1.0 (contact@milkbot.ai)"
NWS_TIMEOUT = 10  # seconds


@dataclass
class CityMarketData:
    """Market data for a single city."""

    city_code: str
    city_name: str
    current_temp: float | None = None
    high_threshold: int | None = None
    yes_bid: int | None = None
    yes_ask: int | None = None
    spread: int | None = None
    volume: int | None = None
    open_interest: int | None = None
    last_signal: str | None = None
    last_signal_time: datetime | None = None
    weather_updated_at: datetime | None = None
    weather_stale: bool = False


@dataclass
class DashboardCache:
    """Simple cache for dashboard data."""

    city_market_data: list[CityMarketData] = field(default_factory=list)
    city_market_data_time: datetime | None = None
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    equity_curve_time: datetime | None = None
    city_metrics: list[dict[str, Any]] = field(default_factory=list)
    city_metrics_time: datetime | None = None
    public_trades: list[dict[str, Any]] = field(default_factory=list)
    public_trades_time: datetime | None = None
    health_status: dict[str, Any] = field(default_factory=dict)
    health_status_time: datetime | None = None

    # Cache TTL in seconds
    ttl_seconds: int = 5


class DashboardDataProvider:
    """Data provider for dashboard components.

    Provides cached access to analytics data with configurable TTL.
    In production, this would connect to the analytics API.
    For now, it provides sample/mock data for testing.
    """

    def __init__(self, cache_ttl: int = 5) -> None:
        """Initialize data provider.

        Args:
            cache_ttl: Cache time-to-live in seconds
        """
        self._cache = DashboardCache(ttl_seconds=cache_ttl)
        self._engine = None  # Would be set in production
        logger.info("dashboard_data_provider_initialized", cache_ttl=cache_ttl)

    def _is_cache_valid(self, cache_time: datetime | None) -> bool:
        """Check if cache entry is still valid."""
        if cache_time is None:
            return False
        age = (datetime.now(timezone.utc) - cache_time).total_seconds()
        return age < self._cache.ttl_seconds

    def get_city_codes(self) -> list[str]:
        """Get list of all city codes."""
        try:
            cities = city_loader.get_all_cities()
            return list(cities.keys())
        except Exception:
            # Fallback to hardcoded list
            return ["NYC", "LAX", "CHI", "MIA", "DFW", "DEN", "PHX", "SEA", "ATL", "BOS"]

    def _fetch_nws_observation(self, station_id: str) -> tuple[float | None, datetime | None]:
        """Fetch current observation from NWS for a station.
        
        Args:
            station_id: ICAO station code (e.g., KORD, KJFK)
            
        Returns:
            Tuple of (temperature_fahrenheit, observation_timestamp)
        """
        try:
            url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
            headers = {"User-Agent": NWS_USER_AGENT}
            response = requests.get(url, headers=headers, timeout=NWS_TIMEOUT)
            
            if response.status_code == 200:
                props = response.json().get("properties", {})
                temp_c = props.get("temperature", {}).get("value")
                timestamp_str = props.get("timestamp")
                
                temp_f = None
                if temp_c is not None:
                    temp_f = round(temp_c * 9/5 + 32, 1)
                
                obs_time = None
                if timestamp_str:
                    try:
                        obs_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    except Exception:
                        pass
                
                return temp_f, obs_time
            else:
                logger.warning("nws_observation_error", station=station_id, status=response.status_code)
                return None, None
        except Exception as e:
            logger.warning("nws_observation_exception", station=station_id, error=str(e))
            return None, None

    def get_city_market_data(self) -> list[CityMarketData]:
        """Get market data for all cities with real NWS weather.

        Returns:
            List of CityMarketData for all 10 cities
        """
        # Check cache
        if self._is_cache_valid(self._cache.city_market_data_time):
            return self._cache.city_market_data

        city_codes = self.get_city_codes()
        market_data = []
        now = datetime.now(timezone.utc)

        for city_code in city_codes:
            try:
                city_config = city_loader.get_city(city_code)
                city_name = city_config.name if city_config else city_code
                station_id = city_config.settlement_station if city_config else None
            except Exception:
                city_name = city_code
                station_id = None

            # Fetch real weather from NWS
            current_temp = None
            weather_time = None
            weather_stale = False
            
            if station_id:
                current_temp, weather_time = self._fetch_nws_observation(station_id)
                if weather_time:
                    age_minutes = (now - weather_time).total_seconds() / 60
                    # NWS updates hourly, so >90 minutes is stale
                    weather_stale = age_minutes > 90
            
            # Market data (placeholder - would come from Kalshi API in production)
            # For now, generate sensible placeholder until trader populates DB
            import random
            random.seed(hash(city_code + now.strftime("%Y%m%d%H")))  # Stable within the hour
            
            market_data.append(
                CityMarketData(
                    city_code=city_code,
                    city_name=city_name,
                    current_temp=current_temp,
                    high_threshold=None,
                    yes_bid=random.randint(35, 65),
                    yes_ask=random.randint(40, 70),
                    spread=random.randint(2, 6),
                    volume=random.randint(800, 4000),
                    open_interest=random.randint(15000, 45000),
                    last_signal=random.choice(["BUY", "SELL", "HOLD"]),
                    last_signal_time=now - timedelta(minutes=random.randint(5, 60)),
                    weather_updated_at=weather_time,
                    weather_stale=weather_stale,
                )
            )

        # Update cache
        self._cache.city_market_data = market_data
        self._cache.city_market_data_time = datetime.now(timezone.utc)

        return market_data

    def get_equity_curve(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get equity curve data for charting.

        Args:
            start_date: Start date for data
            end_date: End date for data

        Returns:
            List of equity curve points
        """
        # Check cache (simple, doesn't account for date range changes)
        if self._is_cache_valid(self._cache.equity_curve_time):
            return self._cache.equity_curve

        # Generate sample data for testing
        # In production, this would call the analytics API
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        import random

        equity_curve = []
        current_equity = 5000.0
        cumulative_pnl = 0.0
        high_water_mark = current_equity

        current_date = start_date
        while current_date <= end_date:
            daily_pnl = random.uniform(-100, 150)
            current_equity += daily_pnl
            cumulative_pnl += daily_pnl
            high_water_mark = max(high_water_mark, current_equity)
            drawdown = high_water_mark - current_equity

            equity_curve.append({
                "date": current_date.isoformat(),
                "ending_equity": round(current_equity, 2),
                "daily_pnl": round(daily_pnl, 2),
                "cumulative_pnl": round(cumulative_pnl, 2),
                "drawdown": round(drawdown, 2),
                "drawdown_pct": round((drawdown / high_water_mark) * 100, 2) if high_water_mark > 0 else 0,
                "high_water_mark": round(high_water_mark, 2),
            })

            current_date += timedelta(days=1)

        # Update cache
        self._cache.equity_curve = equity_curve
        self._cache.equity_curve_time = datetime.now(timezone.utc)

        return equity_curve

    def get_city_metrics(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get city performance metrics.

        Args:
            start_date: Start date for data
            end_date: End date for data

        Returns:
            List of city metrics
        """
        # Check cache
        if self._is_cache_valid(self._cache.city_metrics_time):
            return self._cache.city_metrics

        # Generate sample data for testing
        # In production, this would call the analytics API
        city_codes = self.get_city_codes()
        metrics = []

        import random

        for city_code in city_codes:
            trade_count = random.randint(10, 100)
            win_count = random.randint(5, trade_count)
            loss_count = trade_count - win_count

            metrics.append({
                "city_code": city_code,
                "trade_count": trade_count,
                "win_count": win_count,
                "loss_count": loss_count,
                "win_rate": round((win_count / trade_count) * 100, 1) if trade_count > 0 else 0,
                "net_pnl": round(random.uniform(-500, 1500), 2),
                "gross_pnl": round(random.uniform(0, 2000), 2),
                "fees": round(random.uniform(10, 100), 2),
            })

        # Update cache
        self._cache.city_metrics = metrics
        self._cache.city_metrics_time = datetime.now(timezone.utc)

        return metrics

    def get_public_trades(
        self,
        city_code: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get public trade feed (60-minute delayed).

        Args:
            city_code: Optional city filter
            limit: Maximum trades to return

        Returns:
            List of public trades
        """
        # Check cache
        if self._is_cache_valid(self._cache.public_trades_time):
            trades = self._cache.public_trades
            if city_code:
                trades = [t for t in trades if t.get("city_code") == city_code]
            return trades[:limit]

        # Generate sample data for testing
        # In production, this would call the analytics API
        city_codes = self.get_city_codes()
        trades = []

        import random

        # Generate 100 sample trades
        for i in range(100):
            city = random.choice(city_codes)
            trade_time = datetime.now(timezone.utc) - timedelta(
                minutes=random.randint(60, 1440)  # 1-24 hours ago
            )

            trades.append({
                "trade_id": 1000 + i,
                "city_code": city,
                "ticker": f"HIGH{city}-{trade_time.strftime('%d%b%y').upper()}-T{random.randint(30,70)}",
                "side": random.choice(["yes", "no"]),
                "action": "buy",
                "quantity": random.randint(10, 500),
                "price": random.randint(30, 70),
                "trade_time": trade_time.isoformat(),
                "realized_pnl": round(random.uniform(-50, 100), 2) if random.random() > 0.5 else None,
                "strategy_name": "daily_high_temp",
            })

        # Sort by time descending
        trades.sort(key=lambda t: t["trade_time"], reverse=True)

        # Update cache
        self._cache.public_trades = trades
        self._cache.public_trades_time = datetime.now(timezone.utc)

        # Apply filters
        if city_code:
            trades = [t for t in trades if t.get("city_code") == city_code]

        return trades[:limit]

    def get_health_status(self) -> dict[str, Any]:
        """Get system health status.

        Returns:
            Health status dictionary
        """
        # Check cache
        if self._is_cache_valid(self._cache.health_status_time):
            return self._cache.health_status

        # Generate sample data for testing
        # In production, this would call the analytics API
        import random

        components = [
            {
                "name": "Kalshi API",
                "status": random.choices(["healthy", "degraded", "unhealthy"], weights=[0.9, 0.08, 0.02])[0],
                "last_check": datetime.now(timezone.utc).isoformat(),
                "latency_ms": random.uniform(20, 100),
                "error_rate": random.uniform(0, 0.05),
                "message": None,
            },
            {
                "name": "Weather API (NWS)",
                "status": random.choices(["healthy", "degraded"], weights=[0.95, 0.05])[0],
                "last_check": datetime.now(timezone.utc).isoformat(),
                "latency_ms": random.uniform(50, 200),
                "error_rate": random.uniform(0, 0.02),
                "message": None,
            },
            {
                "name": "Database",
                "status": "healthy",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "latency_ms": random.uniform(5, 20),
                "error_rate": 0,
                "message": None,
            },
            {
                "name": "Trading Engine",
                "status": "healthy",
                "last_check": datetime.now(timezone.utc).isoformat(),
                "latency_ms": random.uniform(10, 50),
                "error_rate": 0,
                "message": None,
            },
        ]

        # Calculate summary
        healthy = sum(1 for c in components if c["status"] == "healthy")
        degraded = sum(1 for c in components if c["status"] == "degraded")
        unhealthy = sum(1 for c in components if c["status"] == "unhealthy")

        # Determine overall status
        if unhealthy > 0:
            overall = "unhealthy"
        elif degraded > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        health_status = {
            "overall_status": overall,
            "components": components,
            "summary": {
                "total_healthy": healthy,
                "total_degraded": degraded,
                "total_unhealthy": unhealthy,
            },
        }

        # Update cache
        self._cache.health_status = health_status
        self._cache.health_status_time = datetime.now(timezone.utc)

        return health_status
