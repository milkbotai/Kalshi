"""Pytest configuration and shared fixtures."""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "requires_db: mark test as requiring database connection"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests marked with requires_db if no database is available."""
    skip_db = pytest.mark.skip(reason="Database not available")

    # Check if database is available
    db_available = False
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="milkbot_test",
            user="milkbot",
            connect_timeout=2,
        )
        conn.close()
        db_available = True
    except Exception:
        pass

    if not db_available:
        for item in items:
            if "requires_db" in item.keywords:
                item.add_marker(skip_db)


@pytest.fixture(autouse=True)
def reset_settings_env() -> None:
    """Reset environment variables before each test."""
    # Store original env vars
    original_env = os.environ.copy()

    # Clear settings-related env vars
    for key in list(os.environ.keys()):
        if key.startswith(("KALSHI_", "DATABASE_", "LOG_", "ENABLE_")):
            del os.environ[key]

    yield

    # Restore original env
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def reset_settings_singleton() -> None:
    """Reset the settings singleton between tests."""
    from src.shared.config import settings as settings_module

    settings_module._settings = None

    yield

    settings_module._settings = None
