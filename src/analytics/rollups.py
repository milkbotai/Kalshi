"""Analytics rollup tables and aggregation functions.

Provides rollup tables for city metrics, strategy metrics, and equity curves
with incremental update capabilities.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.shared.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CityMetrics:
    """Daily metrics for a single city."""

    city_code: str
    date: date
    trade_count: int
    volume: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    fees: Decimal
    win_count: int
    loss_count: int
    avg_position_size: Decimal
    max_position_size: Decimal

    @property
    def win_rate(self) -> float:
        """Calculate win rate as percentage."""
        total = self.win_count + self.loss_count
        if total == 0:
            return 0.0
        return (self.win_count / total) * 100

    @property
    def profit_factor(self) -> float | None:
        """Calculate profit factor (gross wins / gross losses)."""
        if self.loss_count == 0:
            return None
        if self.win_count == 0:
            return 0.0
        # Would need actual win/loss amounts for true profit factor
        return float(self.win_count) / float(self.loss_count)


@dataclass
class StrategyMetrics:
    """Daily metrics for a single strategy."""

    strategy_name: str
    date: date
    signal_count: int
    trade_count: int
    gross_pnl: Decimal
    net_pnl: Decimal
    fees: Decimal
    win_count: int
    loss_count: int
    avg_edge: Decimal
    avg_confidence: Decimal

    @property
    def win_rate(self) -> float:
        """Calculate win rate as percentage."""
        total = self.win_count + self.loss_count
        if total == 0:
            return 0.0
        return (self.win_count / total) * 100

    @property
    def conversion_rate(self) -> float:
        """Calculate signal to trade conversion rate."""
        if self.signal_count == 0:
            return 0.0
        return (self.trade_count / self.signal_count) * 100


@dataclass
class EquityCurvePoint:
    """Single point on the equity curve."""

    date: date
    starting_equity: Decimal
    ending_equity: Decimal
    daily_pnl: Decimal
    cumulative_pnl: Decimal
    drawdown: Decimal
    drawdown_pct: Decimal
    high_water_mark: Decimal


# SQL for creating rollup tables
CITY_METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analytics.city_metrics_daily (
    id SERIAL PRIMARY KEY,
    city_code VARCHAR(3) NOT NULL,
    date DATE NOT NULL,
    trade_count INTEGER NOT NULL DEFAULT 0,
    volume DECIMAL(18, 2) NOT NULL DEFAULT 0,
    gross_pnl DECIMAL(18, 2) NOT NULL DEFAULT 0,
    net_pnl DECIMAL(18, 2) NOT NULL DEFAULT 0,
    fees DECIMAL(18, 2) NOT NULL DEFAULT 0,
    win_count INTEGER NOT NULL DEFAULT 0,
    loss_count INTEGER NOT NULL DEFAULT 0,
    avg_position_size DECIMAL(18, 2) DEFAULT 0,
    max_position_size DECIMAL(18, 2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(city_code, date)
);

CREATE INDEX IF NOT EXISTS idx_city_metrics_city_code
ON analytics.city_metrics_daily(city_code);

CREATE INDEX IF NOT EXISTS idx_city_metrics_date
ON analytics.city_metrics_daily(date);

COMMENT ON TABLE analytics.city_metrics_daily IS
'Daily aggregated metrics per city for performance tracking';
"""

STRATEGY_METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analytics.strategy_metrics_daily (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    signal_count INTEGER NOT NULL DEFAULT 0,
    trade_count INTEGER NOT NULL DEFAULT 0,
    gross_pnl DECIMAL(18, 2) NOT NULL DEFAULT 0,
    net_pnl DECIMAL(18, 2) NOT NULL DEFAULT 0,
    fees DECIMAL(18, 2) NOT NULL DEFAULT 0,
    win_count INTEGER NOT NULL DEFAULT 0,
    loss_count INTEGER NOT NULL DEFAULT 0,
    avg_edge DECIMAL(8, 4) DEFAULT 0,
    avg_confidence DECIMAL(8, 4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(strategy_name, date)
);

CREATE INDEX IF NOT EXISTS idx_strategy_metrics_strategy
ON analytics.strategy_metrics_daily(strategy_name);

CREATE INDEX IF NOT EXISTS idx_strategy_metrics_date
ON analytics.strategy_metrics_daily(date);

COMMENT ON TABLE analytics.strategy_metrics_daily IS
'Daily aggregated metrics per strategy for strategy comparison';
"""

EQUITY_CURVE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analytics.equity_curve_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    starting_equity DECIMAL(18, 2) NOT NULL,
    ending_equity DECIMAL(18, 2) NOT NULL,
    daily_pnl DECIMAL(18, 2) NOT NULL DEFAULT 0,
    cumulative_pnl DECIMAL(18, 2) NOT NULL DEFAULT 0,
    drawdown DECIMAL(18, 2) NOT NULL DEFAULT 0,
    drawdown_pct DECIMAL(8, 4) NOT NULL DEFAULT 0,
    high_water_mark DECIMAL(18, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_equity_curve_date
ON analytics.equity_curve_daily(date);

COMMENT ON TABLE analytics.equity_curve_daily IS
'Daily equity curve for portfolio performance tracking and charting';
"""


def create_rollup_tables(engine: Engine) -> None:
    """Create all rollup tables in the analytics schema.

    Args:
        engine: SQLAlchemy engine instance
    """
    # Ensure analytics schema exists
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
        conn.commit()

    # Create city metrics table
    with engine.connect() as conn:
        for statement in CITY_METRICS_TABLE_SQL.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()
    logger.info("city_metrics_table_created")

    # Create strategy metrics table
    with engine.connect() as conn:
        for statement in STRATEGY_METRICS_TABLE_SQL.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()
    logger.info("strategy_metrics_table_created")

    # Create equity curve table
    with engine.connect() as conn:
        for statement in EQUITY_CURVE_TABLE_SQL.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()
    logger.info("equity_curve_table_created")


def update_city_metrics(
    engine: Engine,
    target_date: date | None = None,
) -> int:
    """Update city metrics rollup for a specific date.

    Performs incremental update - only processes trades for the given date.

    Args:
        engine: SQLAlchemy engine instance
        target_date: Date to process (defaults to today)

    Returns:
        Number of city records updated
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    # Aggregate trades by city for the target date
    aggregate_sql = """
    INSERT INTO analytics.city_metrics_daily (
        city_code, date, trade_count, volume, gross_pnl, net_pnl, fees,
        win_count, loss_count, avg_position_size, max_position_size
    )
    SELECT
        m.city_code,
        DATE(t.executed_at) as trade_date,
        COUNT(*) as trade_count,
        SUM(t.total_cost) as volume,
        SUM(COALESCE(t.realized_pnl, 0)) as gross_pnl,
        SUM(COALESCE(t.realized_pnl, 0) - t.fees) as net_pnl,
        SUM(t.fees) as fees,
        SUM(CASE WHEN COALESCE(t.realized_pnl, 0) > 0 THEN 1 ELSE 0 END) as win_count,
        SUM(CASE WHEN COALESCE(t.realized_pnl, 0) < 0 THEN 1 ELSE 0 END) as loss_count,
        AVG(t.quantity) as avg_position_size,
        MAX(t.quantity) as max_position_size
    FROM trades t
    JOIN markets m ON t.market_id = m.id
    WHERE DATE(t.executed_at) = :target_date
    GROUP BY m.city_code, DATE(t.executed_at)
    ON CONFLICT (city_code, date)
    DO UPDATE SET
        trade_count = EXCLUDED.trade_count,
        volume = EXCLUDED.volume,
        gross_pnl = EXCLUDED.gross_pnl,
        net_pnl = EXCLUDED.net_pnl,
        fees = EXCLUDED.fees,
        win_count = EXCLUDED.win_count,
        loss_count = EXCLUDED.loss_count,
        avg_position_size = EXCLUDED.avg_position_size,
        max_position_size = EXCLUDED.max_position_size,
        updated_at = NOW()
    """

    with engine.connect() as conn:
        result = conn.execute(text(aggregate_sql), {"target_date": target_date})
        affected = result.rowcount
        conn.commit()

    logger.info(
        "city_metrics_updated",
        date=target_date.isoformat(),
        records_affected=affected,
    )

    return affected


def update_strategy_metrics(
    engine: Engine,
    target_date: date | None = None,
) -> int:
    """Update strategy metrics rollup for a specific date.

    Performs incremental update - only processes trades for the given date.

    Args:
        engine: SQLAlchemy engine instance
        target_date: Date to process (defaults to today)

    Returns:
        Number of strategy records updated
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    # Aggregate trades by strategy for the target date
    aggregate_sql = """
    INSERT INTO analytics.strategy_metrics_daily (
        strategy_name, date, signal_count, trade_count, gross_pnl, net_pnl, fees,
        win_count, loss_count, avg_edge, avg_confidence
    )
    SELECT
        COALESCE(t.strategy_name, 'unknown') as strategy_name,
        DATE(t.executed_at) as trade_date,
        COUNT(*) as signal_count,  -- Assuming 1:1 signal:trade for now
        COUNT(*) as trade_count,
        SUM(COALESCE(t.realized_pnl, 0)) as gross_pnl,
        SUM(COALESCE(t.realized_pnl, 0) - t.fees) as net_pnl,
        SUM(t.fees) as fees,
        SUM(CASE WHEN COALESCE(t.realized_pnl, 0) > 0 THEN 1 ELSE 0 END) as win_count,
        SUM(CASE WHEN COALESCE(t.realized_pnl, 0) < 0 THEN 1 ELSE 0 END) as loss_count,
        0 as avg_edge,  -- Would need signal data
        0 as avg_confidence  -- Would need signal data
    FROM trades t
    WHERE DATE(t.executed_at) = :target_date
    GROUP BY COALESCE(t.strategy_name, 'unknown'), DATE(t.executed_at)
    ON CONFLICT (strategy_name, date)
    DO UPDATE SET
        signal_count = EXCLUDED.signal_count,
        trade_count = EXCLUDED.trade_count,
        gross_pnl = EXCLUDED.gross_pnl,
        net_pnl = EXCLUDED.net_pnl,
        fees = EXCLUDED.fees,
        win_count = EXCLUDED.win_count,
        loss_count = EXCLUDED.loss_count,
        avg_edge = EXCLUDED.avg_edge,
        avg_confidence = EXCLUDED.avg_confidence,
        updated_at = NOW()
    """

    with engine.connect() as conn:
        result = conn.execute(text(aggregate_sql), {"target_date": target_date})
        affected = result.rowcount
        conn.commit()

    logger.info(
        "strategy_metrics_updated",
        date=target_date.isoformat(),
        records_affected=affected,
    )

    return affected


def update_equity_curve(
    engine: Engine,
    target_date: date | None = None,
    initial_equity: Decimal = Decimal("1500.00"),
) -> bool:
    """Update equity curve for a specific date.

    Calculates daily P&L, cumulative P&L, drawdown, and high water mark.
    Handles gaps in trading days gracefully.

    Args:
        engine: SQLAlchemy engine instance
        target_date: Date to process (defaults to today)
        initial_equity: Starting equity for first entry

    Returns:
        True if record was created/updated
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    # Get previous day's equity curve entry
    prev_sql = """
    SELECT ending_equity, cumulative_pnl, high_water_mark
    FROM analytics.equity_curve_daily
    WHERE date < :target_date
    ORDER BY date DESC
    LIMIT 1
    """

    with engine.connect() as conn:
        result = conn.execute(text(prev_sql), {"target_date": target_date})
        prev_row = result.fetchone()

    if prev_row:
        starting_equity = Decimal(str(prev_row[0]))
        prev_cumulative = Decimal(str(prev_row[1]))
        prev_hwm = Decimal(str(prev_row[2]))
    else:
        starting_equity = initial_equity
        prev_cumulative = Decimal("0")
        prev_hwm = initial_equity

    # Calculate daily P&L from trades
    pnl_sql = """
    SELECT COALESCE(SUM(realized_pnl - fees), 0) as daily_pnl
    FROM trades
    WHERE DATE(executed_at) = :target_date
    """

    with engine.connect() as conn:
        result = conn.execute(text(pnl_sql), {"target_date": target_date})
        row = result.fetchone()
        daily_pnl = Decimal(str(row[0])) if row else Decimal("0")

    # Calculate metrics
    ending_equity = starting_equity + daily_pnl
    cumulative_pnl = prev_cumulative + daily_pnl
    high_water_mark = max(prev_hwm, ending_equity)
    drawdown = high_water_mark - ending_equity
    drawdown_pct = (drawdown / high_water_mark * 100) if high_water_mark > 0 else Decimal("0")

    # Insert or update
    upsert_sql = """
    INSERT INTO analytics.equity_curve_daily (
        date, starting_equity, ending_equity, daily_pnl, cumulative_pnl,
        drawdown, drawdown_pct, high_water_mark
    ) VALUES (
        :date, :starting_equity, :ending_equity, :daily_pnl, :cumulative_pnl,
        :drawdown, :drawdown_pct, :high_water_mark
    )
    ON CONFLICT (date)
    DO UPDATE SET
        starting_equity = EXCLUDED.starting_equity,
        ending_equity = EXCLUDED.ending_equity,
        daily_pnl = EXCLUDED.daily_pnl,
        cumulative_pnl = EXCLUDED.cumulative_pnl,
        drawdown = EXCLUDED.drawdown,
        drawdown_pct = EXCLUDED.drawdown_pct,
        high_water_mark = EXCLUDED.high_water_mark,
        updated_at = NOW()
    """

    with engine.connect() as conn:
        conn.execute(
            text(upsert_sql),
            {
                "date": target_date,
                "starting_equity": float(starting_equity),
                "ending_equity": float(ending_equity),
                "daily_pnl": float(daily_pnl),
                "cumulative_pnl": float(cumulative_pnl),
                "drawdown": float(drawdown),
                "drawdown_pct": float(drawdown_pct),
                "high_water_mark": float(high_water_mark),
            },
        )
        conn.commit()

    logger.info(
        "equity_curve_updated",
        date=target_date.isoformat(),
        daily_pnl=float(daily_pnl),
        ending_equity=float(ending_equity),
        drawdown_pct=float(drawdown_pct),
    )

    return True


def get_city_metrics(
    engine: Engine,
    city_code: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Query city metrics from rollup table.

    Args:
        engine: SQLAlchemy engine instance
        city_code: Optional filter by city
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of city metrics dictionaries
    """
    query = "SELECT * FROM analytics.city_metrics_daily WHERE 1=1"
    params: dict[str, Any] = {}

    if city_code:
        query += " AND city_code = :city_code"
        params["city_code"] = city_code

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date DESC, city_code"

    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]


def get_strategy_metrics(
    engine: Engine,
    strategy_name: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Query strategy metrics from rollup table.

    Args:
        engine: SQLAlchemy engine instance
        strategy_name: Optional filter by strategy
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of strategy metrics dictionaries
    """
    query = "SELECT * FROM analytics.strategy_metrics_daily WHERE 1=1"
    params: dict[str, Any] = {}

    if strategy_name:
        query += " AND strategy_name = :strategy_name"
        params["strategy_name"] = strategy_name

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date DESC, strategy_name"

    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]


def get_equity_curve(
    engine: Engine,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Query equity curve for charting.

    Args:
        engine: SQLAlchemy engine instance
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of equity curve points as dictionaries
    """
    query = "SELECT * FROM analytics.equity_curve_daily WHERE 1=1"
    params: dict[str, Any] = {}

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date ASC"

    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]


def run_daily_rollups(engine: Engine, target_date: date | None = None) -> dict[str, int]:
    """Run all daily rollup updates.

    Convenience function to update all rollup tables for a given date.

    Args:
        engine: SQLAlchemy engine instance
        target_date: Date to process (defaults to today)

    Returns:
        Dictionary with counts of records updated per rollup type
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    results = {
        "city_metrics": update_city_metrics(engine, target_date),
        "strategy_metrics": update_strategy_metrics(engine, target_date),
        "equity_curve": 1 if update_equity_curve(engine, target_date) else 0,
    }

    logger.info(
        "daily_rollups_completed",
        date=target_date.isoformat(),
        results=results,
    )

    return results
