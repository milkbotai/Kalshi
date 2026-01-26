"""API clients for external services."""

from src.shared.api.errors import (
    APIError,
    AuthenticationError,
    ConnectionError,
    DataError,
    DNSError,
    ErrorCode,
    HTTPError,
    NetworkError,
    RateLimitError,
    TimeoutError,
    classify_error,
    get_retry_delay,
    is_retryable,
)
from src.shared.api.kalshi import KalshiClient
from src.shared.api.nws import NWSClient
from src.shared.api.rate_limiter import RateLimiterManager, TokenBucket, get_rate_limiter_manager

__all__ = [
    "NWSClient",
    "KalshiClient",
    "TokenBucket",
    "RateLimiterManager",
    "get_rate_limiter_manager",
    "APIError",
    "NetworkError",
    "TimeoutError",
    "ConnectionError",
    "DNSError",
    "HTTPError",
    "AuthenticationError",
    "RateLimitError",
    "DataError",
    "ErrorCode",
    "classify_error",
    "is_retryable",
    "get_retry_delay",
]
