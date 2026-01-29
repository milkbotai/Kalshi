"""Internal Analytics API for dashboard queries.

Provides HTTP endpoints for querying analytics data including
city metrics, strategy metrics, equity curve, and health status.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any

from src.shared.config.logging import get_logger

logger = get_logger(__name__)

# Cache TTL in seconds
CACHE_TTL = 5


@dataclass
class APIResponse:
    """Standard API response wrapper."""

    success: bool
    data: Any = None
    error: str | None = None
    timestamp: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class AnalyticsAPI:
    """Internal Analytics API for dashboard queries.

    Provides methods for querying analytics data. Can be used directly
    or wrapped in an HTTP framework (FastAPI, Flask, etc.).
    """

    def __init__(self, engine: Any) -> None:
        """Initialize Analytics API.

        Args:
            engine: SQLAlchemy engine instance
        """
        self.engine = engine
        self._cache: dict[str, tuple[datetime, Any]] = {}
        logger.info("analytics_api_initialized")

    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if still valid."""
        if key in self._cache:
            cached_time, cached_value = self._cache[key]
            age = (datetime.now(timezone.utc) - cached_time).total_seconds()
            if age < CACHE_TTL:
                logger.debug("cache_hit", key=key, age_seconds=age)
                return cached_value
            else:
                logger.debug("cache_expired", key=key, age_seconds=age)
                del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any) -> None:
        """Set cached value with current timestamp."""
        self._cache[key] = (datetime.now(timezone.utc), value)
        logger.debug("cache_set", key=key)

    def get_city_metrics(
        self,
        city_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> APIResponse:
        """Get city performance metrics.

        Args:
            city_code: Optional filter by city
            start_date: Optional start date
            end_date: Optional end date
            limit: Maximum records to return

        Returns:
            APIResponse with city metrics data
        """
        # Check cache
        cache_key = f"city_metrics:{city_code}:{start_date}:{end_date}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            from src.analytics.rollups import get_city_metrics

            metrics = get_city_metrics(
                self.engine,
                city_code=city_code,
                start_date=start_date,
                end_date=end_date,
            )

            # Calculate summary stats
            if metrics:
                total_pnl = sum(m.get("net_pnl", 0) for m in metrics)
                total_trades = sum(m.get("trade_count", 0) for m in metrics)
                total_wins = sum(m.get("win_count", 0) for m in metrics)
                total_losses = sum(m.get("loss_count", 0) for m in metrics)

                summary = {
                    "total_pnl": float(total_pnl),
                    "total_trades": total_trades,
                    "win_rate": (total_wins / (total_wins + total_losses) * 100)
                    if (total_wins + total_losses) > 0
                    else 0,
                }
            else:
                summary = {"total_pnl": 0, "total_trades": 0, "win_rate": 0}

            response = APIResponse(
                success=True,
                data={
                    "metrics": metrics[:limit],
                    "summary": summary,
                    "count": len(metrics),
                },
            )
            
            # Cache successful response
            self._set_cache(cache_key, response)
            return response

        except Exception as e:
            logger.error("city_metrics_query_failed", error=str(e))
            return APIResponse(success=False, error=str(e))

    def get_strategy_metrics(
        self,
        strategy_name: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> APIResponse:
        """Get strategy performance metrics.

        Args:
            strategy_name: Optional filter by strategy
            start_date: Optional start date
            end_date: Optional end date
            limit: Maximum records to return

        Returns:
            APIResponse with strategy metrics data
        """
        try:
            from src.analytics.rollups import get_strategy_metrics

            metrics = get_strategy_metrics(
                self.engine,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
            )

            # Calculate summary stats
            if metrics:
                total_pnl = sum(m.get("net_pnl", 0) for m in metrics)
                total_trades = sum(m.get("trade_count", 0) for m in metrics)
                total_signals = sum(m.get("signal_count", 0) for m in metrics)

                summary = {
                    "total_pnl": float(total_pnl),
                    "total_trades": total_trades,
                    "total_signals": total_signals,
                    "conversion_rate": (total_trades / total_signals * 100)
                    if total_signals > 0
                    else 0,
                }
            else:
                summary = {
                    "total_pnl": 0,
                    "total_trades": 0,
                    "total_signals": 0,
                    "conversion_rate": 0,
                }

            return APIResponse(
                success=True,
                data={
                    "metrics": metrics[:limit],
                    "summary": summary,
                    "count": len(metrics),
                },
            )

        except Exception as e:
            logger.error("strategy_metrics_query_failed", error=str(e))
            return APIResponse(success=False, error=str(e))

    def get_equity_curve(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> APIResponse:
        """Get equity curve for charting.

        Args:
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            APIResponse with equity curve data
        """
        # Check cache
        cache_key = f"equity_curve:{start_date}:{end_date}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            from src.analytics.rollups import get_equity_curve

            curve = get_equity_curve(
                self.engine,
                start_date=start_date,
                end_date=end_date,
            )

            # Calculate summary stats
            if curve:
                first = curve[0]
                last = curve[-1]
                summary = {
                    "starting_equity": float(first.get("starting_equity", 0)),
                    "ending_equity": float(last.get("ending_equity", 0)),
                    "total_return": float(last.get("cumulative_pnl", 0)),
                    "max_drawdown": max(float(p.get("drawdown", 0)) for p in curve),
                    "max_drawdown_pct": max(
                        float(p.get("drawdown_pct", 0)) for p in curve
                    ),
                    "trading_days": len(curve),
                }
            else:
                summary = {
                    "starting_equity": 0,
                    "ending_equity": 0,
                    "total_return": 0,
                    "max_drawdown": 0,
                    "max_drawdown_pct": 0,
                    "trading_days": 0,
                }

            response = APIResponse(
                success=True,
                data={
                    "curve": curve,
                    "summary": summary,
                },
            )
            
            # Cache successful response
            self._set_cache(cache_key, response)
            return response

        except Exception as e:
            logger.error("equity_curve_query_failed", error=str(e))
            return APIResponse(success=False, error=str(e))

    def get_public_trades(
        self,
        city_code: str | None = None,
        limit: int = 100,
    ) -> APIResponse:
        """Get public trades (60-minute delayed).

        Args:
            city_code: Optional filter by city
            limit: Maximum trades to return

        Returns:
            APIResponse with public trade data
        """
        try:
            from src.shared.db.analytics import get_public_trades

            trades = get_public_trades(
                self.engine,
                limit=limit,
                city_code=city_code,
            )

            return APIResponse(
                success=True,
                data={
                    "trades": trades,
                    "count": len(trades),
                    "delay_minutes": 60,
                },
            )

        except Exception as e:
            logger.error("public_trades_query_failed", error=str(e))
            return APIResponse(success=False, error=str(e))

    def get_health_status(self) -> APIResponse:
        """Get current system health status.

        Returns:
            APIResponse with health status data
        """
        try:
            from src.analytics.health import get_current_health

            health = get_current_health(self.engine)

            return APIResponse(
                success=True,
                data={
                    "overall_status": health.overall_status.value,
                    "components": [
                        {
                            "name": c.name,
                            "status": c.status.value,
                            "last_check": c.last_check.isoformat() if c.last_check else None,
                            "latency_ms": c.latency_ms,
                            "error_rate": c.error_rate,
                            "message": c.message,
                        }
                        for c in health.components
                    ],
                    "summary": {
                        "total_healthy": health.total_healthy,
                        "total_degraded": health.total_degraded,
                        "total_unhealthy": health.total_unhealthy,
                    },
                },
            )

        except Exception as e:
            logger.error("health_status_query_failed", error=str(e))
            return APIResponse(success=False, error=str(e))

    def get_degraded_components(self) -> APIResponse:
        """Get list of degraded or unhealthy components.

        Returns:
            APIResponse with degraded component list
        """
        try:
            from src.analytics.health import check_degraded_components

            components = check_degraded_components(self.engine)

            return APIResponse(
                success=True,
                data={
                    "degraded_components": [
                        {
                            "name": c.name,
                            "status": c.status.value,
                            "message": c.message,
                            "latency_ms": c.latency_ms,
                        }
                        for c in components
                    ],
                    "count": len(components),
                },
            )

        except Exception as e:
            logger.error("degraded_components_query_failed", error=str(e))
            return APIResponse(success=False, error=str(e))

    def get_dashboard_summary(self) -> APIResponse:
        """Get combined dashboard summary.

        Aggregates key metrics for the main dashboard view.

        Returns:
            APIResponse with dashboard summary data
        """
        try:
            # Get latest metrics
            city_response = self.get_city_metrics(limit=10)
            strategy_response = self.get_strategy_metrics(limit=10)
            equity_response = self.get_equity_curve()
            health_response = self.get_health_status()

            return APIResponse(
                success=True,
                data={
                    "city_summary": city_response.data.get("summary", {})
                    if city_response.success
                    else {},
                    "strategy_summary": strategy_response.data.get("summary", {})
                    if strategy_response.success
                    else {},
                    "equity_summary": equity_response.data.get("summary", {})
                    if equity_response.success
                    else {},
                    "health_summary": health_response.data.get("summary", {})
                    if health_response.success
                    else {},
                    "overall_health": health_response.data.get("overall_status", "unknown")
                    if health_response.success
                    else "unknown",
                },
            )

        except Exception as e:
            logger.error("dashboard_summary_query_failed", error=str(e))
            return APIResponse(success=False, error=str(e))


def create_analytics_api(engine: Any) -> AnalyticsAPI:
    """Factory function to create AnalyticsAPI instance.

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        Configured AnalyticsAPI instance
    """
    return AnalyticsAPI(engine)
