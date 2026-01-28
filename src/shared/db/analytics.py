"""Analytics schema management and public trade view.

Provides the analytics schema creation and the v_public_trades view
with mandatory 60-minute trade disclosure delay.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.shared.config.logging import get_logger
from src.shared.constants import PUBLIC_TRADE_DELAY_MIN

logger = get_logger(__name__)

# Migration files directory
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def create_analytics_schema(engine: Engine) -> None:
    """Create the analytics schema if it doesn't exist.

    Args:
        engine: SQLAlchemy engine instance
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
        conn.execute(
            text(
                "COMMENT ON SCHEMA analytics IS "
                "'Sanitized views and rollups for public dashboard'"
            )
        )
        conn.commit()

    logger.info("analytics_schema_created")


def create_public_trades_view(engine: Engine) -> None:
    """Create or replace the analytics.v_public_trades view.

    The view enforces the mandatory 60-minute trade delay and redacts
    sensitive information (order_id, intent_key, raw payloads).

    Args:
        engine: SQLAlchemy engine instance
    """
    # Build the view SQL with parameterized delay
    view_sql = f"""
    CREATE OR REPLACE VIEW analytics.v_public_trades AS
    SELECT
        -- Trade identification (anonymized)
        t.id AS trade_id,

        -- Market context
        m.ticker,
        m.city_code,
        m.market_type,
        m.title AS market_title,

        -- Trade details (public)
        t.side,
        t.action,
        t.quantity,
        t.price,
        t.fees,
        t.total_cost,

        -- P&L (when position is closed)
        t.realized_pnl,

        -- Timing (rounded to minute for privacy)
        date_trunc('minute', t.executed_at) AS trade_time,

        -- Strategy (public, for transparency)
        t.strategy_name

    FROM trades t
    JOIN markets m ON t.market_id = m.id

    -- CRITICAL: {PUBLIC_TRADE_DELAY_MIN}-minute delay filter
    WHERE t.executed_at <= (NOW() - INTERVAL '{PUBLIC_TRADE_DELAY_MIN} minutes')

    -- Sorted by time descending
    ORDER BY t.executed_at DESC
    """

    with engine.connect() as conn:
        conn.execute(text(view_sql))
        conn.execute(
            text(
                "COMMENT ON VIEW analytics.v_public_trades IS "
                f"'Public trade feed with mandatory {PUBLIC_TRADE_DELAY_MIN}-minute delay. "
                "Redacts order IDs, intent keys, and raw payloads.'"
            )
        )
        conn.commit()

    logger.info(
        "public_trades_view_created",
        delay_minutes=PUBLIC_TRADE_DELAY_MIN,
    )


def get_public_trades(
    engine: Engine,
    limit: int = 100,
    city_code: str | None = None,
) -> list[dict[str, Any]]:
    """Query public trades from the analytics view.

    Args:
        engine: SQLAlchemy engine instance
        limit: Maximum number of trades to return
        city_code: Optional filter by city code

    Returns:
        List of trade dictionaries with public fields only
    """
    query = "SELECT * FROM analytics.v_public_trades"
    params: dict[str, Any] = {"limit": limit}

    if city_code:
        query += " WHERE city_code = :city_code"
        params["city_code"] = city_code

    query += " LIMIT :limit"

    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        trades = [dict(row._mapping) for row in result]

    logger.debug(
        "public_trades_queried",
        count=len(trades),
        city_code=city_code,
    )

    return trades


def verify_delay_enforcement(engine: Engine) -> bool:
    """Verify that the 60-minute delay is properly enforced.

    This is a safety check that can be run periodically to ensure
    no recent trades are exposed through the public view.

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        True if delay is properly enforced, False if recent trades are exposed
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=PUBLIC_TRADE_DELAY_MIN)

    # Check if any trades in the view are newer than the cutoff
    check_sql = """
    SELECT COUNT(*) as recent_count
    FROM analytics.v_public_trades
    WHERE trade_time > :cutoff
    """

    with engine.connect() as conn:
        result = conn.execute(text(check_sql), {"cutoff": cutoff})
        row = result.fetchone()
        recent_count = row[0] if row else 0

    if recent_count > 0:
        logger.error(
            "delay_enforcement_failure",
            recent_trades_exposed=recent_count,
            cutoff=cutoff.isoformat(),
        )
        return False

    logger.debug("delay_enforcement_verified", cutoff=cutoff.isoformat())
    return True


def run_migrations(engine: Engine) -> None:
    """Run all SQL migrations in order.

    Args:
        engine: SQLAlchemy engine instance
    """
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    for migration_file in migration_files:
        logger.info("running_migration", file=migration_file.name)

        sql = migration_file.read_text()

        with engine.connect() as conn:
            # Execute each statement separately
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement and not statement.startswith("--"):
                    conn.execute(text(statement))
            conn.commit()

        logger.info("migration_completed", file=migration_file.name)
