"""Application settings and environment configuration.

Uses pydantic-settings to load and validate configuration from environment
variables with type safety and validation.
"""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings are loaded from .env file or environment variables.
    Required settings will raise validation errors if missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )

    # Kalshi API
    kalshi_api_key: str = Field(
        default="",
        description="Kalshi API key for authentication",
    )
    kalshi_api_secret: str = Field(
        default="",
        description="Kalshi API secret for authentication",
    )
    kalshi_base_url: str = Field(
        default="https://api.kalshi.com/v1",
        description="Kalshi API base URL",
    )

    # Database
    database_url: str = Field(
        default="postgresql://localhost/milkbot_test",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Database connection pool size",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "console"] = Field(
        default="json",
        description="Log output format",
    )

    # Trading parameters
    max_position_size: int = Field(
        default=1000,
        ge=1,
        description="Maximum contracts per position",
    )
    min_edge_bps: int = Field(
        default=50,
        ge=0,
        description="Minimum edge in basis points",
    )

    # Feature flags
    enable_trading: bool = Field(
        default=False,
        description="Enable live trading (False for dry-run mode)",
    )
    enable_analytics: bool = Field(
        default=True,
        description="Enable analytics collection",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL uses postgresql scheme."""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("Database URL must use postgresql:// scheme")
        return v


# Global settings instance - will be lazy loaded or use defaults
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For backwards compatibility
settings = get_settings()
