"""Application settings and environment configuration.

Uses pydantic-settings to load and validate configuration from environment
variables with type safety and validation.
"""

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(Enum):
    """Trading mode enumeration.

    SHADOW: Signals generated, no orders submitted, simulated fills
    DEMO: Uses demo API keys and endpoints
    LIVE: Uses production keys (requires explicit confirmation)
    """

    SHADOW = "shadow"
    DEMO = "demo"
    LIVE = "live"


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

    # Trading mode
    trading_mode: TradingMode = Field(
        default=TradingMode.SHADOW,
        description="Trading mode: shadow (no trades), demo, or live",
    )

    # Kalshi API (RSA Key Authentication)
    kalshi_api_key_id: str | None = Field(
        default=None,
        description="Kalshi API key ID for RSA authentication",
    )
    kalshi_private_key_path: str | None = Field(
        default=None,
        description="Path to Kalshi RSA private key file (.pem)",
    )
    kalshi_api_url: str = Field(
        default="https://demo-api.kalshi.co/trade-api/v2",
        description="Kalshi API URL (demo or production)",
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
    db_pool_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Database connection pool size (alias)",
    )
    db_max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum overflow connections beyond pool size",
    )
    db_pool_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Connection pool timeout in seconds",
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
    bankroll: float = Field(
        default=992.10,
        ge=0,
        description="Starting bankroll in dollars",
    )
    max_position_size: int = Field(
        default=200,
        ge=1,
        description="Maximum contracts per position",
    )
    min_edge_bps: int = Field(
        default=50,
        ge=0,
        description="Minimum edge in basis points",
    )
    max_trade_risk_pct: float = Field(
        default=0.02,
        ge=0,
        le=1,
        description="Maximum risk per trade as percentage of bankroll",
    )
    max_city_exposure_pct: float = Field(
        default=0.03,
        ge=0,
        le=1,
        description="Maximum exposure per city as percentage of bankroll",
    )
    max_daily_loss_pct: float = Field(
        default=0.05,
        ge=0,
        le=1,
        description="Maximum daily loss as percentage of bankroll",
    )

    # Execution gates
    spread_max_cents: int = Field(
        default=4,
        ge=1,
        description="Maximum acceptable spread in cents",
    )
    min_edge_after_costs: float = Field(
        default=0.03,
        ge=0,
        description="Minimum edge after costs as fraction",
    )
    liquidity_min: int = Field(
        default=500,
        ge=0,
        description="Minimum market liquidity (volume + open interest)",
    )

    # Trading loop timing
    cycle_interval_sec: int = Field(
        default=300,
        ge=10,
        description="Seconds between trading cycles",
    )
    error_sleep_sec: int = Field(
        default=60,
        ge=5,
        description="Seconds to sleep after an error before retrying",
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
