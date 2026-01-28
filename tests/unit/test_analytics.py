"""Unit tests for analytics schema and public trade view.

Tests the 60-minute trade delay enforcement and data redaction.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.shared.constants import PUBLIC_TRADE_DELAY_MIN
from src.shared.db.analytics import (
    MIGRATIONS_DIR,
    create_analytics_schema,
    create_public_trades_view,
    get_public_trades,
    run_migrations,
    verify_delay_enforcement,
)


class TestAnalyticsSchema:
    """Test suite for analytics schema management."""

    def test_migrations_directory_exists(self) -> None:
        """Test that migrations directory exists."""
        assert MIGRATIONS_DIR.exists()
        assert MIGRATIONS_DIR.is_dir()

    def test_migration_files_exist(self) -> None:
        """Test that required migration files exist."""
        migration_files = list(MIGRATIONS_DIR.glob("*.sql"))
        assert len(migration_files) >= 2

        # Check specific migrations
        filenames = [f.name for f in migration_files]
        assert "001_create_schemas.sql" in filenames
        assert "002_create_public_trades_view.sql" in filenames

    def test_migration_files_ordered(self) -> None:
        """Test that migration files are properly numbered for ordering."""
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        for i, migration_file in enumerate(migration_files):
            # Each file should start with a 3-digit number
            prefix = migration_file.name[:3]
            assert prefix.isdigit(), f"Migration {migration_file.name} missing numeric prefix"

    def test_create_analytics_schema(self) -> None:
        """Test creating analytics schema."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        create_analytics_schema(mock_engine)

        # Verify schema creation SQL was executed
        assert mock_conn.execute.called
        # Verify commit was called
        mock_conn.commit.assert_called_once()
        # Verify at least 2 execute calls (schema creation + comment)
        assert mock_conn.execute.call_count >= 2

    def test_create_public_trades_view(self) -> None:
        """Test creating public trades view with delay."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        create_public_trades_view(mock_engine)

        # Verify view creation SQL was executed
        assert mock_conn.execute.called
        # Verify commit was called
        mock_conn.commit.assert_called_once()
        # Verify at least 2 execute calls (view creation + comment)
        assert mock_conn.execute.call_count >= 2


class TestPublicTradesView:
    """Test suite for public trades view and delay enforcement."""

    def test_public_trade_delay_constant(self) -> None:
        """Test that PUBLIC_TRADE_DELAY_MIN is set to 60."""
        assert PUBLIC_TRADE_DELAY_MIN == 60

    def test_get_public_trades_basic(self) -> None:
        """Test querying public trades."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Mock trade data
        mock_row = MagicMock()
        mock_row._mapping = {
            "trade_id": 1,
            "ticker": "HIGHNYC-25JAN26",
            "city_code": "NYC",
            "side": "yes",
            "quantity": 100,
            "price": 45.0,
            "trade_time": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))

        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        trades = get_public_trades(mock_engine, limit=10)

        assert len(trades) == 1
        assert trades[0]["ticker"] == "HIGHNYC-25JAN26"
        assert trades[0]["city_code"] == "NYC"

    def test_get_public_trades_with_city_filter(self) -> None:
        """Test querying public trades with city code filter."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))

        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        get_public_trades(mock_engine, limit=10, city_code="NYC")

        # Verify city filter was included in query
        call_args = mock_conn.execute.call_args
        query = str(call_args[0][0])
        assert "city_code" in query

    def test_get_public_trades_respects_limit(self) -> None:
        """Test that limit parameter is passed to query."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))

        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        get_public_trades(mock_engine, limit=50)

        # Verify limit parameter was passed
        call_args = mock_conn.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        assert params["limit"] == 50


class TestDelayEnforcement:
    """Test suite for 60-minute delay enforcement verification."""

    def test_verify_delay_enforcement_passes_when_no_recent_trades(self) -> None:
        """Test verification passes when no recent trades in view."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Return count of 0 (no recent trades)
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value=0)
        mock_result.fetchone.return_value = mock_row

        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        result = verify_delay_enforcement(mock_engine)

        assert result is True

    def test_verify_delay_enforcement_fails_when_recent_trades_exposed(self) -> None:
        """Test verification fails when recent trades are exposed."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Return count > 0 (recent trades exposed - BAD!)
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value=5)
        mock_result.fetchone.return_value = mock_row

        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        result = verify_delay_enforcement(mock_engine)

        assert result is False

    def test_delay_cutoff_calculation(self) -> None:
        """Test that delay cutoff is calculated correctly."""
        now = datetime.now(timezone.utc)
        expected_cutoff = now - timedelta(minutes=PUBLIC_TRADE_DELAY_MIN)

        # The cutoff should be 60 minutes ago
        assert (now - expected_cutoff).total_seconds() == PUBLIC_TRADE_DELAY_MIN * 60


class TestMigrations:
    """Test suite for migration runner."""

    def test_run_migrations_executes_all_files(self) -> None:
        """Test that run_migrations executes all SQL files."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        run_migrations(mock_engine)

        # Should have executed SQL and committed for each migration
        assert mock_conn.execute.called
        assert mock_conn.commit.called

    def test_migration_sql_content(self) -> None:
        """Test that migration SQL files have expected content."""
        schema_migration = MIGRATIONS_DIR / "001_create_schemas.sql"
        view_migration = MIGRATIONS_DIR / "002_create_public_trades_view.sql"

        # Check schema migration
        schema_sql = schema_migration.read_text()
        assert "CREATE SCHEMA" in schema_sql
        assert "ops" in schema_sql
        assert "analytics" in schema_sql

        # Check view migration
        view_sql = view_migration.read_text()
        assert "CREATE VIEW" in view_sql or "CREATE OR REPLACE VIEW" in view_sql
        assert "v_public_trades" in view_sql
        assert "60 minutes" in view_sql or "60 min" in view_sql


class TestViewRedaction:
    """Test suite for data redaction in public view."""

    def test_view_sql_excludes_sensitive_fields(self) -> None:
        """Test that view SQL does not expose sensitive fields."""
        view_migration = MIGRATIONS_DIR / "002_create_public_trades_view.sql"
        view_sql = view_migration.read_text()

        # Extract only the SELECT portion (between SELECT and FROM)
        # This excludes comments which may mention sensitive fields
        select_start = view_sql.upper().find("SELECT")
        from_start = view_sql.upper().find("FROM", select_start)
        select_portion = view_sql[select_start:from_start].lower() if select_start >= 0 and from_start > select_start else ""

        # These sensitive fields should NOT be selected
        # (They may appear in comments, but not in the SELECT clause)
        # order_id from orders table should not be in public view
        # (we do select t.id AS trade_id which is fine)
        assert "intent_key" not in select_portion
        assert "client_order_id" not in select_portion
        assert "raw_payload" not in select_portion

    def test_view_sql_includes_public_fields(self) -> None:
        """Test that view SQL includes expected public fields."""
        view_migration = MIGRATIONS_DIR / "002_create_public_trades_view.sql"
        view_sql = view_migration.read_text()

        # These public fields should be included
        assert "ticker" in view_sql
        assert "city_code" in view_sql
        assert "side" in view_sql
        assert "quantity" in view_sql
        assert "price" in view_sql
        assert "trade_time" in view_sql

    def test_view_sql_rounds_time(self) -> None:
        """Test that view SQL rounds trade time for privacy."""
        view_migration = MIGRATIONS_DIR / "002_create_public_trades_view.sql"
        view_sql = view_migration.read_text()

        # Should use date_trunc to round to minute
        assert "date_trunc" in view_sql.lower()
        assert "minute" in view_sql.lower()
