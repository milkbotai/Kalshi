"""Centralized error handling for API clients.

Provides custom exception hierarchy with error codes, retry hints,
and structured logging integration.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from src.shared.config.logging import get_logger

logger = get_logger(__name__)


class ErrorCode(Enum):
    """Error codes for API exceptions."""

    # Network errors (1xxx)
    NETWORK_TIMEOUT = 1001
    NETWORK_CONNECTION = 1002
    NETWORK_DNS = 1003
    NETWORK_SSL = 1004

    # HTTP errors (2xxx)
    HTTP_BAD_REQUEST = 2400
    HTTP_UNAUTHORIZED = 2401
    HTTP_FORBIDDEN = 2403
    HTTP_NOT_FOUND = 2404
    HTTP_RATE_LIMIT = 2429
    HTTP_SERVER_ERROR = 2500
    HTTP_BAD_GATEWAY = 2502
    HTTP_SERVICE_UNAVAILABLE = 2503
    HTTP_GATEWAY_TIMEOUT = 2504

    # Authentication errors (3xxx)
    AUTH_INVALID_CREDENTIALS = 3001
    AUTH_TOKEN_EXPIRED = 3002
    AUTH_TOKEN_INVALID = 3003

    # Data errors (4xxx)
    DATA_INVALID_RESPONSE = 4001
    DATA_PARSE_ERROR = 4002
    DATA_VALIDATION_ERROR = 4003

    # Rate limiting errors (5xxx)
    RATE_LIMIT_EXCEEDED = 5001
    RATE_LIMIT_QUOTA_EXCEEDED = 5002

    # Unknown/Other
    UNKNOWN_ERROR = 9999


class APIError(Exception):
    """Base exception for all API errors.

    Provides structured error information including error codes,
    retry hints, and context for logging.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        retryable: bool = False,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize API error.

        Args:
            message: Human-readable error message
            error_code: Structured error code
            retryable: Whether the operation can be retried
            endpoint: API endpoint that failed
            details: Additional error context
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.retryable = retryable
        self.endpoint = endpoint
        self.details = details or {}
        self.timestamp = datetime.utcnow()

        # Log the error
        logger.error(
            "api_error",
            error_code=error_code.name,
            message=message,
            retryable=retryable,
            endpoint=endpoint,
            details=details,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for serialization.

        Returns:
            Dictionary representation of error
        """
        return {
            "error_code": self.error_code.name,
            "error_value": self.error_code.value,
            "message": self.message,
            "retryable": self.retryable,
            "endpoint": self.endpoint,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class NetworkError(APIError):
    """Network-related errors (timeouts, connection failures, DNS)."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.NETWORK_CONNECTION,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize network error.

        Args:
            message: Error message
            error_code: Specific network error code
            endpoint: Failed endpoint
            details: Additional context
        """
        super().__init__(
            message=message,
            error_code=error_code,
            retryable=True,  # Network errors are generally retryable
            endpoint=endpoint,
            details=details,
        )


class TimeoutError(NetworkError):
    """Request timeout error."""

    def __init__(
        self,
        endpoint: str | None = None,
        timeout_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize timeout error.

        Args:
            endpoint: Failed endpoint
            timeout_seconds: Timeout duration
            details: Additional context
        """
        details = details or {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=(
                f"Request timed out after {timeout_seconds}s"
                if timeout_seconds
                else "Request timed out"
            ),
            error_code=ErrorCode.NETWORK_TIMEOUT,
            endpoint=endpoint,
            details=details,
        )


class ConnectionError(NetworkError):
    """Connection failure error."""

    def __init__(
        self,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize connection error.

        Args:
            endpoint: Failed endpoint
            details: Additional context
        """
        super().__init__(
            message="Failed to establish connection",
            error_code=ErrorCode.NETWORK_CONNECTION,
            endpoint=endpoint,
            details=details,
        )


class DNSError(NetworkError):
    """DNS resolution error."""

    def __init__(
        self,
        hostname: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize DNS error.

        Args:
            hostname: Failed hostname
            details: Additional context
        """
        details = details or {}
        if hostname:
            details["hostname"] = hostname

        super().__init__(
            message=(
                f"DNS resolution failed for {hostname}" if hostname else "DNS resolution failed"
            ),
            error_code=ErrorCode.NETWORK_DNS,
            endpoint=None,
            details=details,
        )


class HTTPError(APIError):
    """HTTP status code errors (4xx, 5xx)."""

    def __init__(
        self,
        message: str,
        status_code: int,
        error_code: ErrorCode | None = None,
        endpoint: str | None = None,
        response_body: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize HTTP error.

        Args:
            message: Error message
            status_code: HTTP status code
            error_code: Specific error code (auto-detected if None)
            endpoint: Failed endpoint
            response_body: Response body text
            details: Additional context
        """
        details = details or {}
        details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body

        # Auto-detect error code from status code
        if error_code is None:
            error_code = self._error_code_from_status(status_code)

        # Determine if retryable based on status code
        retryable = status_code in [429, 500, 502, 503, 504]

        super().__init__(
            message=message,
            error_code=error_code,
            retryable=retryable,
            endpoint=endpoint,
            details=details,
        )
        self.status_code = status_code

    @staticmethod
    def _error_code_from_status(status_code: int) -> ErrorCode:
        """Map HTTP status code to error code.

        Args:
            status_code: HTTP status code

        Returns:
            Corresponding ErrorCode
        """
        mapping = {
            400: ErrorCode.HTTP_BAD_REQUEST,
            401: ErrorCode.HTTP_UNAUTHORIZED,
            403: ErrorCode.HTTP_FORBIDDEN,
            404: ErrorCode.HTTP_NOT_FOUND,
            429: ErrorCode.HTTP_RATE_LIMIT,
            500: ErrorCode.HTTP_SERVER_ERROR,
            502: ErrorCode.HTTP_BAD_GATEWAY,
            503: ErrorCode.HTTP_SERVICE_UNAVAILABLE,
            504: ErrorCode.HTTP_GATEWAY_TIMEOUT,
        }
        return mapping.get(status_code, ErrorCode.UNKNOWN_ERROR)


class AuthenticationError(APIError):
    """Authentication and authorization errors."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.AUTH_INVALID_CREDENTIALS,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize authentication error.

        Args:
            message: Error message
            error_code: Specific auth error code
            endpoint: Failed endpoint
            details: Additional context
        """
        super().__init__(
            message=message,
            error_code=error_code,
            retryable=False,  # Auth errors generally not retryable
            endpoint=endpoint,
            details=details,
        )


class RateLimitError(APIError):
    """Rate limiting errors."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retry
            endpoint: Failed endpoint
            details: Additional context
        """
        details = details or {}
        if retry_after is not None:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            retryable=True,
            endpoint=endpoint,
            details=details,
        )
        self.retry_after = retry_after


class DataError(APIError):
    """Data validation and parsing errors."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.DATA_INVALID_RESPONSE,
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize data error.

        Args:
            message: Error message
            error_code: Specific data error code
            endpoint: Failed endpoint
            details: Additional context
        """
        super().__init__(
            message=message,
            error_code=error_code,
            retryable=False,  # Data errors generally not retryable
            endpoint=endpoint,
            details=details,
        )


def classify_error(exception: Exception, endpoint: str | None = None) -> APIError:
    """Classify a generic exception into an APIError.

    Args:
        exception: Exception to classify
        endpoint: API endpoint that failed

    Returns:
        Classified APIError instance
    """
    import requests

    # Already an APIError
    if isinstance(exception, APIError):
        return exception

    # Requests library exceptions
    if isinstance(exception, requests.Timeout):
        return TimeoutError(endpoint=endpoint)

    if isinstance(exception, requests.ConnectionError):
        return ConnectionError(endpoint=endpoint)

    if isinstance(exception, requests.HTTPError):
        response = getattr(exception, "response", None)
        status_code = response.status_code if response else 500
        return HTTPError(
            message=str(exception),
            status_code=status_code,
            endpoint=endpoint,
        )

    # Generic exception
    return APIError(
        message=str(exception),
        error_code=ErrorCode.UNKNOWN_ERROR,
        endpoint=endpoint,
        details={"exception_type": type(exception).__name__},
    )


def is_retryable(error: Exception) -> bool:
    """Check if an error is retryable.

    Args:
        error: Exception to check

    Returns:
        True if error is retryable
    """
    if isinstance(error, APIError):
        return error.retryable

    # Classify and check
    classified = classify_error(error)
    return classified.retryable


def get_retry_delay(error: Exception, attempt: int = 0) -> float:
    """Calculate retry delay for an error.

    Args:
        error: Exception that occurred
        attempt: Retry attempt number (0-indexed)

    Returns:
        Delay in seconds before retry
    """
    # Rate limit errors may specify retry_after
    if isinstance(error, RateLimitError) and error.retry_after:
        return float(error.retry_after)

    # Exponential backoff: 1s, 2s, 4s, 8s, ...
    return min(2**attempt, 60)  # Cap at 60 seconds
