"""Shared fixtures for integration tests."""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring external services"
    )
    config.addinivalue_line("markers", "slow: mark test as slow-running")


@pytest.fixture(scope="session")
def skip_if_no_kalshi_credentials() -> None:
    """Skip test if Kalshi credentials are not configured."""
    api_key_id = os.getenv("KALSHI_API_KEY_ID")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")

    if not api_key_id or not private_key_path:
        pytest.skip("Kalshi API credentials not configured. Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH.")
