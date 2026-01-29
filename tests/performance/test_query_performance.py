"""Performance tests for critical database queries.

Tests query performance and establishes baselines for regression detection.
"""

import time
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.shared.db.connection import DatabaseManager


class TestQueryPerformance:
    """Performance tests for database queries."""

    @pytest.fixture(scope="class")
    def engine(self) -> Engine:
        """Get database engine."""
        db_manager = DatabaseManager()
        return db_manager.get_engine()

    def test_city_metrics_query_performance(self, engine: Engine) -> None:
        """Test city metrics query performance."""
        query = text("""
            SELECT 
                city_code,
                COUNT(*) as trade_count,
                SUM(realized_pnl) as total_pnl,
                AVG(realized_pnl) as avg_pnl
            FROM ops.trades
            WHERE created_at >= :start_date
            GROUP BY city_code
            ORDER BY total_pnl DESC
        """)

        start_date = date.today() - timedelta(days=30)

        start_time = time.time()
        with engine.connect() as conn:
            result = conn.execute(query, {"start_date": start_date})
            rows = result.fetchall()
        elapsed = time.time() - start_time

        # Should complete in under 100ms for 30 days of data
        assert elapsed < 0.1, f"Query took {elapsed:.3f}s, expected < 0.1s"
        print(f"City metrics query: {elapsed*1000:.1f}ms ({len(rows)} rows)")

    def test_equity_curve_query_performance(self, engine: Engine) -> None:
        """Test equity curve query performance."""
        query = text("""
            SELECT 
                date,
                ending_equity,
                daily_pnl,
                cumulative_pnl
            FROM analytics.equity_curve
            WHERE date >= :start_date
            ORDER BY date ASC
        """)

        start_date = date.today() - timedelta(days=90)

        start_time = time.time()
        with engine.connect() as conn:
            result = conn.execute(query, {"start_date": start_date})
            rows = result.fetchall()
        elapsed = time.time() - start_time

        # Should complete in under 50ms for 90 days
        assert elapsed < 0.05, f"Query took {elapsed:.3f}s, expected < 0.05s"
        print(f"Equity curve query: {elapsed*1000:.1f}ms ({len(rows)} rows)")

    def test_public_trades_query_performance(self, engine: Engine) -> None:
        """Test public trades query with 60-minute delay."""
        query = text("""
            SELECT 
                t.ticker,
                t.side,
                t.quantity,
                t.price,
                t.created_at
            FROM ops.trades t
            WHERE t.created_at <= NOW() - INTERVAL '60 minutes'
            ORDER BY t.created_at DESC
            LIMIT 100
        """)

        start_time = time.time()
        with engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()
        elapsed = time.time() - start_time

        # Should complete in under 50ms
        assert elapsed < 0.05, f"Query took {elapsed:.3f}s, expected < 0.05s"
        print(f"Public trades query: {elapsed*1000:.1f}ms ({len(rows)} rows)")

    def test_health_status_query_performance(self, engine: Engine) -> None:
        """Test health status query performance."""
        query = text("""
            SELECT 
                component,
                status,
                last_check,
                message
            FROM ops.health_status
            ORDER BY last_check DESC
        """)

        start_time = time.time()
        with engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()
        elapsed = time.time() - start_time

        # Should complete in under 20ms
        assert elapsed < 0.02, f"Query took {elapsed:.3f}s, expected < 0.02s"
        print(f"Health status query: {elapsed*1000:.1f}ms ({len(rows)} rows)")

    def test_strategy_metrics_aggregation_performance(self, engine: Engine) -> None:
        """Test strategy metrics aggregation performance."""
        query = text("""
            SELECT 
                strategy_name,
                COUNT(*) as signal_count,
                COUNT(CASE WHEN decision != 'HOLD' THEN 1 END) as trade_count,
                AVG(edge) as avg_edge
            FROM ops.signals
            WHERE created_at >= :start_date
            GROUP BY strategy_name
        """)

        start_date = date.today() - timedelta(days=30)

        start_time = time.time()
        with engine.connect() as conn:
            result = conn.execute(query, {"start_date": start_date})
            rows = result.fetchall()
        elapsed = time.time() - start_time

        # Should complete in under 100ms
        assert elapsed < 0.1, f"Query took {elapsed:.3f}s, expected < 0.1s"
        print(f"Strategy metrics query: {elapsed*1000:.1f}ms ({len(rows)} rows)")


class TestCachePerformance:
    """Performance tests for caching layer."""

    def test_cache_hit_performance(self) -> None:
        """Test cache hit performance."""
        from src.analytics.api import AnalyticsAPI
        from src.shared.db.connection import DatabaseManager

        db_manager = DatabaseManager()
        engine = db_manager.get_engine()
        api = AnalyticsAPI(engine)

        # First call (cache miss)
        start_time = time.time()
        response1 = api.get_city_metrics(limit=10)
        first_call = time.time() - start_time

        # Second call (cache hit)
        start_time = time.time()
        response2 = api.get_city_metrics(limit=10)
        second_call = time.time() - start_time

        # Cache hit should be at least 10x faster
        assert second_call < first_call / 10, \
            f"Cache hit ({second_call*1000:.1f}ms) not significantly faster than miss ({first_call*1000:.1f}ms)"
        
        print(f"Cache miss: {first_call*1000:.1f}ms, Cache hit: {second_call*1000:.1f}ms")
        print(f"Speedup: {first_call/second_call:.1f}x")


def run_performance_baseline() -> None:
    """Run all performance tests and record baseline."""
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_performance_baseline()
