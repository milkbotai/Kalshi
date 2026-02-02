"""Data provider for dashboard.

Provides data access layer for the Streamlit dashboard,
connecting to the Kalshi API for real portfolio/trade data and NWS weather data.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from src.shared.api.kalshi import KalshiClient
from src.shared.config.cities import city_loader
from src.shared.config.logging import get_logger

logger = get_logger(__name__)

# City code mapping from Kalshi ticker prefixes
# Kalshi uses KXHIGH prefix with abbreviated city codes
TICKER_TO_CITY = {
    "KXHIGHNY": "NYC",
    "KXHIGHLA": "LAX",
    "KXHIGHCHI": "CHI",
    "KXHIGHMIA": "MIA",
    "KXHIGHAUS": "AUS",
    "KXHIGHDEN": "DEN",
    "KXHIGHPHIL": "PHL",
    "KXHIGHSEA": "SEA",
    "KXHIGHBOS": "BOS",
    "KXHIGHSFO": "SFO",
}

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
    win_rate: float | None = None
    net_pnl: float | None = None


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


def _extract_city_from_ticker(ticker: str) -> str | None:
    """Extract city code from a Kalshi ticker like HIGHNYC-26JAN31-T45."""
    for prefix, city_code in TICKER_TO_CITY.items():
        if ticker.startswith(prefix):
            return city_code
    return None


class DashboardDataProvider:
    """Data provider for dashboard components.

    Provides cached access to real Kalshi API data with configurable TTL.
    Fetches portfolio balance, fills, and positions from Kalshi demo API.
    """

    def __init__(self, cache_ttl: int = 5) -> None:
        """Initialize data provider with Kalshi API client.

        Args:
            cache_ttl: Cache time-to-live in seconds
        """
        self._cache = DashboardCache(ttl_seconds=cache_ttl)
        self._kalshi_client: KalshiClient | None = None
        self._init_kalshi_client()
        logger.info("dashboard_data_provider_initialized", cache_ttl=cache_ttl)

    def _init_kalshi_client(self) -> None:
        """Initialize Kalshi API client from environment."""
        api_key_id = os.environ.get("KALSHI_API_KEY_ID")
        private_key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH")
        api_url = os.environ.get("KALSHI_API_URL", os.environ.get("KALSHI_API_BASE", "https://demo-api.kalshi.co/trade-api/v2"))

        if api_key_id and private_key_path:
            try:
                self._kalshi_client = KalshiClient(
                    api_key_id=api_key_id,
                    private_key_path=private_key_path,
                    base_url=api_url,
                )
                logger.info("kalshi_client_initialized_for_dashboard")
            except Exception as e:
                logger.warning("kalshi_client_init_failed", error=str(e))
                self._kalshi_client = None
        else:
            logger.warning("kalshi_credentials_not_configured",
                          has_key_id=bool(api_key_id),
                          has_key_path=bool(private_key_path))

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

    def _fetch_kalshi_markets_for_city(self, city_code: str) -> dict[str, Any] | None:
        """Fetch current market data for a city from Kalshi API."""
        if not self._kalshi_client:
            return None

        try:
            # Kalshi series ticker format: KXHIGH{CITY} with abbreviated city codes
            city_ticker_map = {
                "NYC": "NY",
                "CHI": "CHI",
                "LAX": "LA",
                "MIA": "MIA",
                "AUS": "AUS",
                "DEN": "DEN",
                "PHL": "PHIL",
                "BOS": "BOS",
                "SEA": "SEA",
                "SFO": "SFO",
            }
            kalshi_city = city_ticker_map.get(city_code, city_code)
            series_ticker = f"KXHIGH{kalshi_city}"
            markets = self._kalshi_client.get_markets(series_ticker=series_ticker, status="open", limit=1)

            if markets:
                return markets[0]
            return None
        except Exception as e:
            logger.warning("kalshi_market_fetch_error", city=city_code, error=str(e))
            return None

    def get_city_market_data(self) -> list[CityMarketData]:
        """Get market data for all cities with real NWS weather and Kalshi prices.

        Returns:
            List of CityMarketData for all 10 cities
        """
        # Check cache
        if self._is_cache_valid(self._cache.city_market_data_time):
            return self._cache.city_market_data

        city_codes = self.get_city_codes()
        market_data = []
        now = datetime.now(timezone.utc)

        # Get city metrics for win rate and P&L data
        city_metrics = self.get_city_metrics()
        metrics_by_city = {m["city_code"]: m for m in city_metrics}

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

            # Fetch real market data from Kalshi
            kalshi_market = self._fetch_kalshi_markets_for_city(city_code)

            # Get win rate and P&L from real city metrics
            city_metric = metrics_by_city.get(city_code, {})
            win_rate = city_metric.get("win_rate", 0.0)
            net_pnl = city_metric.get("net_pnl", 0.0)

            if kalshi_market:
                # Use real market data
                yes_bid = kalshi_market.get("yes_bid")
                yes_ask = kalshi_market.get("yes_ask")
                spread = (yes_ask - yes_bid) if yes_bid and yes_ask else None
                volume = kalshi_market.get("volume", 0)
                open_interest = kalshi_market.get("open_interest", 0)
            else:
                # No market available (markets closed or error)
                yes_bid = None
                yes_ask = None
                spread = None
                volume = 0
                open_interest = 0

            market_data.append(
                CityMarketData(
                    city_code=city_code,
                    city_name=city_name,
                    current_temp=current_temp,
                    high_threshold=None,
                    yes_bid=yes_bid,
                    yes_ask=yes_ask,
                    spread=spread,
                    volume=volume,
                    open_interest=open_interest,
                    last_signal=None,  # Would come from strategy state
                    last_signal_time=None,
                    weather_updated_at=weather_time,
                    weather_stale=weather_stale,
                    win_rate=win_rate,
                    net_pnl=net_pnl,
                )
            )

        # Update cache
        self._cache.city_market_data = market_data
        self._cache.city_market_data_time = datetime.now(timezone.utc)

        logger.info("city_market_data_built", cities=len(market_data))

        return market_data

    def _fetch_kalshi_fills(self) -> list[dict[str, Any]]:
        """Fetch all fills from Kalshi API."""
        if not self._kalshi_client:
            logger.warning("kalshi_client_not_available_for_fills")
            return []

        try:
            # Fetch fills from the last 30 days
            min_ts = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)
            fills = self._kalshi_client.get_fills(min_ts=min_ts, limit=1000)
            logger.info("kalshi_fills_fetched", count=len(fills))
            return fills
        except Exception as e:
            logger.error("kalshi_fills_fetch_error", error=str(e))
            return []

    def _fetch_kalshi_balance(self) -> dict[str, Any]:
        """Fetch current balance from Kalshi API."""
        if not self._kalshi_client:
            logger.warning("kalshi_client_not_available_for_balance")
            return {}

        try:
            balance = self._kalshi_client.get_balance()
            logger.info("kalshi_balance_fetched", balance=balance)
            return balance
        except Exception as e:
            logger.error("kalshi_balance_fetch_error", error=str(e))
            return {}

    def _fetch_kalshi_positions(self) -> list[dict[str, Any]]:
        """Fetch current positions from Kalshi API."""
        if not self._kalshi_client:
            logger.warning("kalshi_client_not_available_for_positions")
            return []

        try:
            positions = self._kalshi_client.get_positions()
            logger.info("kalshi_positions_fetched", count=len(positions))
            return positions
        except Exception as e:
            logger.error("kalshi_positions_fetch_error", error=str(e))
            return []

    def get_equity_curve(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get equity curve data from real Kalshi API data.

        Builds equity curve from actual fills and current balance.

        Args:
            start_date: Start date for data
            end_date: End date for data

        Returns:
            List of equity curve points
        """
        # Check cache
        if self._is_cache_valid(self._cache.equity_curve_time):
            return self._cache.equity_curve

        # Get real data from Kalshi
        balance_data = self._fetch_kalshi_balance()
        fills = self._fetch_kalshi_fills()

        # Starting bankroll from env (default $5000 = 500000 cents)
        starting_bankroll_cents = int(os.environ.get("BANKROLL", "5000")) * 100

        # Current portfolio value from Kalshi (in cents)
        current_balance_cents = balance_data.get("balance", 0)
        portfolio_value_cents = balance_data.get("portfolio_value", current_balance_cents)

        # Total P&L = current value - starting
        total_pnl_cents = portfolio_value_cents - starting_bankroll_cents

        # Build daily equity curve from fills
        launch_date = date(2026, 1, 31)
        if start_date is None:
            start_date = launch_date
        if end_date is None:
            end_date = date.today()

        if start_date < launch_date:
            start_date = launch_date

        # Group fills by date
        daily_pnl: dict[str, float] = {}
        for fill in fills:
            # Parse fill timestamp
            fill_ts = fill.get("created_time") or fill.get("ts")
            if not fill_ts:
                continue

            try:
                if isinstance(fill_ts, int):
                    fill_date = datetime.fromtimestamp(fill_ts / 1000, tz=timezone.utc).date()
                else:
                    fill_date = datetime.fromisoformat(fill_ts.replace("Z", "+00:00")).date()
            except Exception:
                continue

            date_key = fill_date.isoformat()

            # Calculate P&L for this fill
            # Kalshi fills have: side (yes/no), action (buy/sell), count, price
            action = fill.get("action", "")
            side = fill.get("side", "")
            count = fill.get("count", 0)
            price = fill.get("price", 0)  # in cents

            # For settled contracts, we also get 'is_taker' and realized P&L
            # P&L = (exit_price - entry_price) * count for longs
            # For now, use the fill's own P&L if available, otherwise estimate
            fill_pnl = fill.get("realized_pnl", 0)
            if fill_pnl == 0:
                # Estimate: buying YES at price X means we paid X cents per contract
                # If settled at 100, we made (100 - X) per contract
                # This is approximate without knowing settlement
                pass

            if date_key not in daily_pnl:
                daily_pnl[date_key] = 0.0
            daily_pnl[date_key] += fill_pnl / 100.0  # Convert cents to dollars

        # Build equity curve
        equity_curve = []
        current_equity = starting_bankroll_cents / 100.0  # Convert to dollars
        cumulative_pnl = 0.0
        high_water_mark = current_equity

        current_date = start_date
        while current_date <= end_date:
            date_key = current_date.isoformat()
            day_pnl = daily_pnl.get(date_key, 0.0)

            current_equity += day_pnl
            cumulative_pnl += day_pnl
            high_water_mark = max(high_water_mark, current_equity)
            drawdown = high_water_mark - current_equity

            equity_curve.append({
                "date": date_key,
                "ending_equity": round(current_equity, 2),
                "daily_pnl": round(day_pnl, 2),
                "cumulative_pnl": round(cumulative_pnl, 2),
                "drawdown": round(drawdown, 2),
                "drawdown_pct": round((drawdown / high_water_mark) * 100, 2) if high_water_mark > 0 else 0,
                "high_water_mark": round(high_water_mark, 2),
            })

            current_date += timedelta(days=1)

        # If we have real balance data, update the last point to reflect actual current value
        if equity_curve and portfolio_value_cents > 0:
            actual_equity = portfolio_value_cents / 100.0
            actual_cumulative_pnl = total_pnl_cents / 100.0
            equity_curve[-1]["ending_equity"] = round(actual_equity, 2)
            equity_curve[-1]["cumulative_pnl"] = round(actual_cumulative_pnl, 2)
            # Recalculate drawdown for last point
            high_water_mark = max(high_water_mark, actual_equity)
            equity_curve[-1]["high_water_mark"] = round(high_water_mark, 2)
            equity_curve[-1]["drawdown"] = round(high_water_mark - actual_equity, 2)
            equity_curve[-1]["drawdown_pct"] = round(((high_water_mark - actual_equity) / high_water_mark) * 100, 2) if high_water_mark > 0 else 0

        # Update cache
        self._cache.equity_curve = equity_curve
        self._cache.equity_curve_time = datetime.now(timezone.utc)

        logger.info("equity_curve_built",
                   points=len(equity_curve),
                   current_equity=equity_curve[-1]["ending_equity"] if equity_curve else 0,
                   total_pnl=equity_curve[-1]["cumulative_pnl"] if equity_curve else 0)

        return equity_curve

    def get_city_metrics(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get city performance metrics from real Kalshi fills.

        Aggregates fills by city to compute win rate, P&L, and trade counts.

        Args:
            start_date: Start date for data
            end_date: End date for data

        Returns:
            List of city metrics
        """
        # Check cache
        if self._is_cache_valid(self._cache.city_metrics_time):
            return self._cache.city_metrics

        # Get all city codes
        city_codes = self.get_city_codes()

        # Initialize metrics per city
        city_data: dict[str, dict[str, Any]] = {}
        for city_code in city_codes:
            city_data[city_code] = {
                "city_code": city_code,
                "trade_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "net_pnl": 0.0,
                "gross_pnl": 0.0,
                "fees": 0.0,
            }

        # Fetch real fills from Kalshi
        fills = self._fetch_kalshi_fills()

        # Aggregate fills by city
        for fill in fills:
            ticker = fill.get("ticker", "")
            city_code = _extract_city_from_ticker(ticker)

            if not city_code or city_code not in city_data:
                continue

            # Increment trade count
            city_data[city_code]["trade_count"] += 1

            # Get P&L for this fill
            realized_pnl = fill.get("realized_pnl", 0) / 100.0  # Convert cents to dollars

            # Track wins/losses based on P&L
            if realized_pnl > 0:
                city_data[city_code]["win_count"] += 1
                city_data[city_code]["gross_pnl"] += realized_pnl
            elif realized_pnl < 0:
                city_data[city_code]["loss_count"] += 1

            city_data[city_code]["net_pnl"] += realized_pnl

            # Estimate fees (Kalshi charges ~$0.01-0.02 per contract)
            count = fill.get("count", 0)
            city_data[city_code]["fees"] += count * 0.01

        # Calculate win rates and format output
        metrics = []
        for city_code in city_codes:
            data = city_data[city_code]
            trade_count = data["trade_count"]

            if trade_count > 0:
                win_rate = (data["win_count"] / trade_count) * 100
            else:
                win_rate = 0.0

            metrics.append({
                "city_code": city_code,
                "trade_count": trade_count,
                "win_count": data["win_count"],
                "loss_count": data["loss_count"],
                "win_rate": round(win_rate, 1),
                "net_pnl": round(data["net_pnl"], 2),
                "gross_pnl": round(data["gross_pnl"], 2),
                "fees": round(data["fees"], 2),
            })

        # Update cache
        self._cache.city_metrics = metrics
        self._cache.city_metrics_time = datetime.now(timezone.utc)

        logger.info("city_metrics_built",
                   cities_with_trades=sum(1 for m in metrics if m["trade_count"] > 0),
                   total_trades=sum(m["trade_count"] for m in metrics),
                   total_pnl=sum(m["net_pnl"] for m in metrics))

        return metrics

    def get_public_trades(
        self,
        city_code: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get trade feed from real Kalshi fills (60-minute delayed for public).

        Args:
            city_code: Optional city filter
            limit: Maximum trades to return

        Returns:
            List of trades from Kalshi fills
        """
        # Check cache
        if self._is_cache_valid(self._cache.public_trades_time):
            trades = self._cache.public_trades
            if city_code:
                trades = [t for t in trades if t.get("city_code") == city_code]
            return trades[:limit]

        # Fetch real fills from Kalshi
        fills = self._fetch_kalshi_fills()
        trades = []

        for fill in fills:
            ticker = fill.get("ticker", "")
            extracted_city = _extract_city_from_ticker(ticker)

            # Parse fill timestamp
            fill_ts = fill.get("created_time") or fill.get("ts")
            if fill_ts:
                try:
                    if isinstance(fill_ts, int):
                        trade_time = datetime.fromtimestamp(fill_ts / 1000, tz=timezone.utc)
                    else:
                        trade_time = datetime.fromisoformat(fill_ts.replace("Z", "+00:00"))
                except Exception:
                    trade_time = datetime.now(timezone.utc)
            else:
                trade_time = datetime.now(timezone.utc)

            trades.append({
                "trade_id": fill.get("trade_id") or fill.get("fill_id"),
                "city_code": extracted_city,
                "ticker": ticker,
                "side": fill.get("side", ""),
                "action": fill.get("action", ""),
                "quantity": fill.get("count", 0),
                "price": fill.get("price", 0),
                "trade_time": trade_time.isoformat(),
                "realized_pnl": fill.get("realized_pnl", 0) / 100.0 if fill.get("realized_pnl") else None,
                "strategy_name": "daily_high_temp",
            })

        # Sort by time descending
        trades.sort(key=lambda t: t["trade_time"], reverse=True)

        # Update cache
        self._cache.public_trades = trades
        self._cache.public_trades_time = datetime.now(timezone.utc)

        logger.info("public_trades_built", count=len(trades))

        # Apply filters
        if city_code:
            trades = [t for t in trades if t.get("city_code") == city_code]

        return trades[:limit]

    def get_health_status(self) -> dict[str, Any]:
        """Get system health status by actually checking services.

        Returns:
            Health status dictionary
        """
        # Check cache
        if self._is_cache_valid(self._cache.health_status_time):
            return self._cache.health_status

        now = datetime.now(timezone.utc)
        components = []

        # Check Kalshi API health
        kalshi_status = "healthy"
        kalshi_message = None
        kalshi_latency = 0.0

        if self._kalshi_client:
            try:
                import time
                start = time.time()
                self._kalshi_client.get_balance()
                kalshi_latency = (time.time() - start) * 1000
                kalshi_status = "healthy"
            except Exception as e:
                kalshi_status = "unhealthy"
                kalshi_message = str(e)[:100]
        else:
            kalshi_status = "degraded"
            kalshi_message = "API credentials not configured"

        components.append({
            "name": "Kalshi API",
            "status": kalshi_status,
            "last_check": now.isoformat(),
            "latency_ms": round(kalshi_latency, 2),
            "error_rate": 0,
            "message": kalshi_message,
        })

        # Check NWS API health (use a test station)
        nws_status = "healthy"
        nws_message = None
        nws_latency = 0.0

        try:
            import time
            start = time.time()
            temp, _ = self._fetch_nws_observation("KJFK")
            nws_latency = (time.time() - start) * 1000
            if temp is None:
                nws_status = "degraded"
                nws_message = "No temperature data returned"
        except Exception as e:
            nws_status = "unhealthy"
            nws_message = str(e)[:100]

        components.append({
            "name": "Weather API (NWS)",
            "status": nws_status,
            "last_check": now.isoformat(),
            "latency_ms": round(nws_latency, 2),
            "error_rate": 0,
            "message": nws_message,
        })

        # Dashboard is always healthy if we got here
        components.append({
            "name": "Dashboard",
            "status": "healthy",
            "last_check": now.isoformat(),
            "latency_ms": 0,
            "error_rate": 0,
            "message": None,
        })

        # Check Trading Engine status
        # The trading bot runs separately and scans for opportunities every 5 minutes.
        # We check: 1) Can we reach Kalshi API? 2) Are there any orders/positions?
        # Note: Having 0 orders is normal if the strategy hasn't found good edges yet.
        trading_status = "healthy"
        trading_message = None
        trading_latency = 0.0
        last_activity = None
        orders_today = 0
        last_scan = None
        markets_scanned = 0

        if self._kalshi_client:
            try:
                import time as time_module
                start = time_module.time()

                # Check for orders and positions
                orders = self._kalshi_client.get_orders(status="all")
                positions = self._kalshi_client.get_positions()
                trading_latency = (time_module.time() - start) * 1000

                # Count orders from today
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                recent_orders = [
                    o for o in orders
                    if datetime.fromisoformat(
                        o.get("created_time", "2000-01-01T00:00:00Z").replace("Z", "+00:00")
                    ) > today_start
                ]
                orders_today = len(recent_orders)

                # Get last order time if any orders exist
                if orders:
                    last_order_time = max(
                        datetime.fromisoformat(
                            o.get("created_time", "2000-01-01T00:00:00Z").replace("Z", "+00:00")
                        )
                        for o in orders
                    )
                    last_activity = last_order_time.isoformat()

                # Check for heartbeat file (written by trading bot each cycle)
                import os
                heartbeat_path = os.environ.get("HEARTBEAT_FILE", "/tmp/milkbot_heartbeat.txt")
                if os.path.exists(heartbeat_path):
                    try:
                        with open(heartbeat_path) as f:
                            heartbeat_data = f.read().strip()
                            # Format: ISO timestamp|markets_scanned
                            parts = heartbeat_data.split("|")
                            last_scan = parts[0]
                            if len(parts) > 1:
                                markets_scanned = int(parts[1])

                            # Check if heartbeat is stale (>10 minutes old)
                            heartbeat_time = datetime.fromisoformat(last_scan.replace("Z", "+00:00"))
                            minutes_since_scan = (datetime.now(timezone.utc) - heartbeat_time).total_seconds() / 60

                            if minutes_since_scan > 10:
                                trading_status = "degraded"
                                trading_message = f"Last scan {minutes_since_scan:.0f}m ago"
                    except Exception:
                        pass  # Heartbeat file parse error, ignore

                # If no heartbeat file exists yet, that's okay - bot may be starting up
                # or heartbeat feature not yet deployed
                if last_scan is None:
                    # Fallback: if we can reach API and have balance, assume bot could be running
                    # This is a softer check - we just verify API connectivity
                    trading_message = "Monitoring (waiting for first scan)"

            except Exception as e:
                trading_status = "degraded"
                trading_message = f"API error: {str(e)[:50]}"
        else:
            trading_status = "degraded"
            trading_message = "API not configured"

        components.append({
            "name": "Trading Engine",
            "status": trading_status,
            "last_check": now.isoformat(),
            "latency_ms": round(trading_latency, 2),
            "error_rate": 0,
            "message": trading_message,
            "last_activity": last_activity,
            "orders_today": orders_today,
            "last_scan": last_scan,
            "markets_scanned": markets_scanned,
        })

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
