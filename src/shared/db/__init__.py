"""Database connection, models, and repository pattern implementation."""

from src.shared.db.analytics import (
    create_analytics_schema,
    create_public_trades_view,
    get_public_trades,
    run_migrations,
    verify_delay_enforcement,
)
from src.shared.db.connection import DatabaseManager, get_db
from src.shared.db.models import (
    Base,
    ComponentHealth,
    Fill,
    HealthStatus,
    MarketSnapshot,
    Order,
    OrderStatus,
    Position,
    RiskEvent,
    RiskSeverity,
    Signal,
    TradingModeEnum,
    WeatherSnapshot,
)
from src.shared.db.repositories import (
    BaseRepository,
    FillRepository,
    MarketRepository,
    OrderRepository,
    PositionRepository,
    SignalRepository,
    WeatherRepository,
)


def get_trading_repositories(
    db_manager: DatabaseManager | None = None,
) -> tuple[
    WeatherRepository,
    MarketRepository,
    SignalRepository,
    OrderRepository,
    FillRepository,
    PositionRepository,
]:
    """Get all repository instances for trading operations.

    Creates repositories using the provided DatabaseManager or the global instance.

    Args:
        db_manager: Optional DatabaseManager. If not provided, uses get_db().

    Returns:
        Tuple of (WeatherRepository, MarketRepository, SignalRepository,
                  OrderRepository, FillRepository, PositionRepository)

    Example:
        >>> weather_repo, market_repo, signal_repo, order_repo, fill_repo, position_repo = \\
        ...     get_trading_repositories()
        >>> snapshot = weather_repo.get_latest("NYC")
    """
    db = db_manager or get_db()
    return (
        WeatherRepository(db),
        MarketRepository(db),
        SignalRepository(db),
        OrderRepository(db),
        FillRepository(db),
        PositionRepository(db),
    )


__all__ = [
    # Connection management
    "DatabaseManager",
    "get_db",
    # Analytics
    "create_analytics_schema",
    "create_public_trades_view",
    "get_public_trades",
    "run_migrations",
    "verify_delay_enforcement",
    # ORM Base and Models
    "Base",
    "WeatherSnapshot",
    "MarketSnapshot",
    "Signal",
    "Order",
    "Fill",
    "Position",
    "RiskEvent",
    "ComponentHealth",
    # Enums
    "OrderStatus",
    "TradingModeEnum",
    "RiskSeverity",
    "HealthStatus",
    # Repositories
    "BaseRepository",
    "WeatherRepository",
    "MarketRepository",
    "SignalRepository",
    "OrderRepository",
    "FillRepository",
    "PositionRepository",
    # Factory functions
    "get_trading_repositories",
]
