"""Unit tests for settings configuration."""

import pytest
from pydantic import ValidationError

from src.shared.config.settings import Settings, get_settings


class TestSettings:
    """Test suite for Settings configuration."""

    def test_settings_has_default_api_credentials(self) -> None:
        """Test that API credentials have defaults for testing."""
        settings = Settings()

        assert settings.kalshi_api_key == ""
        assert settings.kalshi_api_secret == ""

    def test_settings_has_default_database_url(self) -> None:
        """Test that database URL has a default."""
        settings = Settings()

        assert settings.database_url == "postgresql://localhost/milkbot_test"

    def test_settings_validates_database_scheme(self) -> None:
        """Test that database URL must use postgresql scheme."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(database_url="mysql://localhost/test")

        assert any("postgresql" in str(e) for e in exc_info.value.errors())

    def test_settings_with_valid_config(self) -> None:
        """Test settings creation with valid configuration."""
        settings = Settings(
            kalshi_api_key="test_key",
            kalshi_api_secret="test_secret",
            database_url="postgresql://localhost/test",
            environment="development",
            log_level="DEBUG",
        )

        assert settings.kalshi_api_key == "test_key"
        assert settings.kalshi_api_secret == "test_secret"
        assert settings.environment == "development"
        assert settings.log_level == "DEBUG"
        assert settings.enable_trading is False

    def test_settings_default_values(self) -> None:
        """Test that default values are applied correctly."""
        settings = Settings()

        assert settings.environment == "development"
        assert settings.log_level == "INFO"
        assert settings.log_format == "json"
        assert settings.max_position_size == 1000
        assert settings.min_edge_bps == 50
        assert settings.enable_trading is False
        assert settings.enable_analytics is True

    def test_settings_validates_pool_size_range(self) -> None:
        """Test that database pool size is validated."""
        with pytest.raises(ValidationError):
            Settings(database_pool_size=0)

        with pytest.raises(ValidationError):
            Settings(database_pool_size=100)

    def test_get_settings_returns_singleton(self) -> None:
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
