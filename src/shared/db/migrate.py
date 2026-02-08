"""Database migration runner.

Reads SQL migration files from src/shared/db/migrations/ and applies them
in order.  Tracks applied migrations in a `_migrations` table so each
file is executed at most once.

Usage:
    python -m src.shared.db.migrate          # apply all pending migrations
    python -m src.shared.db.migrate --status  # show migration status
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from src.shared.config.logging import get_logger
from src.shared.db.connection import DatabaseManager, get_db

logger = get_logger(__name__)

# Resolve the migrations directory relative to this file
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# SQL to create the tracking table (idempotent)
_CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS _migrations (
    id          SERIAL PRIMARY KEY,
    filename    TEXT UNIQUE NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _ensure_tracking_table(db: DatabaseManager) -> None:
    """Create the _migrations tracking table if it does not exist."""
    with db.engine.connect() as conn:
        conn.execute(text(_CREATE_TRACKING_TABLE))
        conn.commit()


def _get_applied_migrations(db: DatabaseManager) -> set[str]:
    """Return the set of migration filenames that have already been applied."""
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT filename FROM _migrations ORDER BY filename")
        ).fetchall()
    return {row[0] for row in rows}


def _get_pending_migrations(db: DatabaseManager) -> list[Path]:
    """Return migration files sorted by name that have not yet been applied."""
    if not MIGRATIONS_DIR.is_dir():
        logger.warning("migrations_dir_missing", path=str(MIGRATIONS_DIR))
        return []

    applied = _get_applied_migrations(db)
    sql_files = sorted(
        f for f in MIGRATIONS_DIR.iterdir()
        if f.suffix == ".sql" and f.name not in applied
    )
    return sql_files


def _record_migration(db: DatabaseManager, filename: str) -> None:
    """Record a migration as applied in the tracking table."""
    with db.engine.connect() as conn:
        conn.execute(
            text("INSERT INTO _migrations (filename, applied_at) VALUES (:fn, :ts)"),
            {"fn": filename, "ts": datetime.now(timezone.utc)},
        )
        conn.commit()


def run_migrations(db: DatabaseManager | None = None) -> int:
    """Apply all pending SQL migrations in order.

    Args:
        db: DatabaseManager instance.  Uses the global instance when *None*.

    Returns:
        Number of migrations applied.
    """
    db = db or get_db()

    _ensure_tracking_table(db)

    pending = _get_pending_migrations(db)
    if not pending:
        logger.info("no_pending_migrations")
        return 0

    applied_count = 0
    for migration_file in pending:
        logger.info("applying_migration", filename=migration_file.name)
        sql = migration_file.read_text(encoding="utf-8")

        try:
            with db.engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            _record_migration(db, migration_file.name)
            applied_count += 1
            logger.info("migration_applied", filename=migration_file.name)
        except Exception as exc:
            logger.error(
                "migration_failed",
                filename=migration_file.name,
                error=str(exc),
            )
            raise

    logger.info("migrations_complete", applied=applied_count)
    return applied_count


def show_status(db: DatabaseManager | None = None) -> None:
    """Print migration status to stdout."""
    db = db or get_db()

    _ensure_tracking_table(db)

    applied = _get_applied_migrations(db)
    all_files = sorted(
        f.name
        for f in MIGRATIONS_DIR.iterdir()
        if f.suffix == ".sql"
    ) if MIGRATIONS_DIR.is_dir() else []

    print(f"Migrations directory: {MIGRATIONS_DIR}")
    print(f"Total migration files: {len(all_files)}")
    print(f"Applied: {len(applied)}")
    print(f"Pending: {len(all_files) - len(applied)}")
    print()
    for name in all_files:
        status = "APPLIED" if name in applied else "PENDING"
        print(f"  [{status}] {name}")


# ── CLI entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status instead of applying",
    )
    args = parser.parse_args()

    try:
        db = get_db()
        if args.status:
            show_status(db)
        else:
            count = run_migrations(db)
            print(f"Applied {count} migration(s).")
    except Exception as exc:
        logger.error("migration_runner_failed", error=str(exc))
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
