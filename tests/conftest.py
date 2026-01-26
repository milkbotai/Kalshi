"""Pytest configuration and shared fixtures."""

import os

import pytest


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
