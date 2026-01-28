"""Unit tests for API error handling."""

import pytest
import requests

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


class TestErrorCode:
    """Test suite for ErrorCode enum."""

    def test_error_code_values(self) -> None:
        """Test error codes have correct values."""
        assert ErrorCode.NETWORK_TIMEOUT.value == 1001
        assert ErrorCode.HTTP_UNAUTHORIZED.value == 2401
        assert ErrorCode.AUTH_INVALID_CREDENTIALS.value == 3001
        assert ErrorCode.RATE_LIMIT_EXCEEDED.value == 5001


class TestAPIError:
    """Test suite for APIError base class."""

    def test_api_error_creation(self) -> None:
        """Test creating an APIError instance."""
        error = APIError(
            message="Test error",
            error_code=ErrorCode.UNKNOWN_ERROR,
            retryable=True,
            endpoint="/test",
            details={"key": "value"},
        )

        assert error.message == "Test error"
        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert error.retryable is True
        assert error.endpoint == "/test"
        assert error.details == {"key": "value"}
        assert error.timestamp is not None

    def test_api_error_to_dict(self) -> None:
        """Test converting APIError to dictionary."""
        error = APIError(
            message="Test error",
            error_code=ErrorCode.HTTP_NOT_FOUND,
            endpoint="/test",
        )

        error_dict = error.to_dict()

        assert error_dict["error_code"] == "HTTP_NOT_FOUND"
        assert error_dict["error_value"] == 2404
        assert error_dict["message"] == "Test error"
        assert error_dict["retryable"] is False
        assert error_dict["endpoint"] == "/test"
        assert "timestamp" in error_dict

    def test_api_error_default_values(self) -> None:
        """Test APIError with default values."""
        error = APIError(message="Simple error")

        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert error.retryable is False
        assert error.endpoint is None
        assert error.details == {}


class TestNetworkError:
    """Test suite for NetworkError."""

    def test_network_error_creation(self) -> None:
        """Test creating a NetworkError instance."""
        error = NetworkError(
            message="Connection failed",
            error_code=ErrorCode.NETWORK_CONNECTION,
            endpoint="/api/test",
        )

        assert error.message == "Connection failed"
        assert error.error_code == ErrorCode.NETWORK_CONNECTION
        assert error.retryable is True  # Network errors are retryable
        assert error.endpoint == "/api/test"

    def test_network_error_default_retryable(self) -> None:
        """Test NetworkError is retryable by default."""
        error = NetworkError(message="Network issue")

        assert error.retryable is True


class TestTimeoutError:
    """Test suite for TimeoutError."""

    def test_timeout_error_with_duration(self) -> None:
        """Test TimeoutError with timeout duration."""
        error = TimeoutError(endpoint="/api/test", timeout_seconds=30.0)

        assert "30.0s" in error.message
        assert error.error_code == ErrorCode.NETWORK_TIMEOUT
        assert error.retryable is True
        assert error.details["timeout_seconds"] == 30.0

    def test_timeout_error_without_duration(self) -> None:
        """Test TimeoutError without timeout duration."""
        error = TimeoutError(endpoint="/api/test")

        assert "timed out" in error.message.lower()
        assert error.error_code == ErrorCode.NETWORK_TIMEOUT


class TestConnectionError:
    """Test suite for ConnectionError."""

    def test_connection_error_creation(self) -> None:
        """Test creating a ConnectionError instance."""
        error = ConnectionError(endpoint="/api/test")

        assert "connection" in error.message.lower()
        assert error.error_code == ErrorCode.NETWORK_CONNECTION
        assert error.retryable is True


class TestDNSError:
    """Test suite for DNSError."""

    def test_dns_error_with_hostname(self) -> None:
        """Test DNSError with hostname."""
        error = DNSError(hostname="api.example.com")

        assert "api.example.com" in error.message
        assert error.error_code == ErrorCode.NETWORK_DNS
        assert error.details["hostname"] == "api.example.com"

    def test_dns_error_without_hostname(self) -> None:
        """Test DNSError without hostname."""
        error = DNSError()

        assert "DNS" in error.message
        assert error.error_code == ErrorCode.NETWORK_DNS


class TestHTTPError:
    """Test suite for HTTPError."""

    def test_http_error_with_status_code(self) -> None:
        """Test HTTPError with status code."""
        error = HTTPError(
            message="Not found",
            status_code=404,
            endpoint="/api/test",
        )

        assert error.message == "Not found"
        assert error.status_code == 404
        assert error.error_code == ErrorCode.HTTP_NOT_FOUND
        assert error.retryable is False

    def test_http_error_retryable_status_codes(self) -> None:
        """Test HTTPError retryable for 5xx and 429."""
        retryable_codes = [429, 500, 502, 503, 504]

        for code in retryable_codes:
            error = HTTPError(message="Server error", status_code=code)
            assert error.retryable is True, f"Status {code} should be retryable"

    def test_http_error_non_retryable_status_codes(self) -> None:
        """Test HTTPError non-retryable for 4xx (except 429)."""
        non_retryable_codes = [400, 401, 403, 404]

        for code in non_retryable_codes:
            error = HTTPError(message="Client error", status_code=code)
            assert error.retryable is False, f"Status {code} should not be retryable"

    def test_http_error_with_response_body(self) -> None:
        """Test HTTPError with response body."""
        error = HTTPError(
            message="Bad request",
            status_code=400,
            response_body='{"error": "invalid"}',
        )

        assert error.details["response_body"] == '{"error": "invalid"}'

    def test_http_error_auto_detect_error_code(self) -> None:
        """Test HTTPError auto-detects error code from status."""
        test_cases = [
            (400, ErrorCode.HTTP_BAD_REQUEST),
            (401, ErrorCode.HTTP_UNAUTHORIZED),
            (403, ErrorCode.HTTP_FORBIDDEN),
            (404, ErrorCode.HTTP_NOT_FOUND),
            (429, ErrorCode.HTTP_RATE_LIMIT),
            (500, ErrorCode.HTTP_SERVER_ERROR),
            (502, ErrorCode.HTTP_BAD_GATEWAY),
            (503, ErrorCode.HTTP_SERVICE_UNAVAILABLE),
            (504, ErrorCode.HTTP_GATEWAY_TIMEOUT),
        ]

        for status_code, expected_code in test_cases:
            error = HTTPError(message="Test", status_code=status_code)
            assert error.error_code == expected_code


class TestAuthenticationError:
    """Test suite for AuthenticationError."""

    def test_authentication_error_creation(self) -> None:
        """Test creating an AuthenticationError instance."""
        error = AuthenticationError(
            message="Invalid credentials",
            error_code=ErrorCode.AUTH_INVALID_CREDENTIALS,
        )

        assert error.message == "Invalid credentials"
        assert error.error_code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert error.retryable is False

    def test_authentication_error_token_expired(self) -> None:
        """Test AuthenticationError for expired token."""
        error = AuthenticationError(
            message="Token expired",
            error_code=ErrorCode.AUTH_TOKEN_EXPIRED,
        )

        assert error.error_code == ErrorCode.AUTH_TOKEN_EXPIRED


class TestRateLimitError:
    """Test suite for RateLimitError."""

    def test_rate_limit_error_with_retry_after(self) -> None:
        """Test RateLimitError with retry_after."""
        error = RateLimitError(
            message="Rate limit exceeded",
            retry_after=60,
            endpoint="/api/test",
        )

        assert error.message == "Rate limit exceeded"
        assert error.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert error.retryable is True
        assert error.retry_after == 60
        assert error.details["retry_after"] == 60

    def test_rate_limit_error_without_retry_after(self) -> None:
        """Test RateLimitError without retry_after."""
        error = RateLimitError(message="Rate limit exceeded")

        assert error.retry_after is None


class TestDataError:
    """Test suite for DataError."""

    def test_data_error_creation(self) -> None:
        """Test creating a DataError instance."""
        error = DataError(
            message="Invalid JSON",
            error_code=ErrorCode.DATA_PARSE_ERROR,
        )

        assert error.message == "Invalid JSON"
        assert error.error_code == ErrorCode.DATA_PARSE_ERROR
        assert error.retryable is False


class TestClassifyError:
    """Test suite for classify_error function."""

    def test_classify_api_error(self) -> None:
        """Test classifying an existing APIError."""
        original = APIError(message="Test", error_code=ErrorCode.UNKNOWN_ERROR)
        classified = classify_error(original)

        assert classified is original

    def test_classify_requests_timeout(self) -> None:
        """Test classifying requests.Timeout."""
        exception = requests.Timeout("Request timed out")
        classified = classify_error(exception, endpoint="/api/test")

        assert isinstance(classified, TimeoutError)
        assert classified.error_code == ErrorCode.NETWORK_TIMEOUT
        assert classified.endpoint == "/api/test"

    def test_classify_requests_connection_error(self) -> None:
        """Test classifying requests.ConnectionError."""
        exception = requests.ConnectionError("Connection failed")
        classified = classify_error(exception, endpoint="/api/test")

        assert isinstance(classified, ConnectionError)
        assert classified.error_code == ErrorCode.NETWORK_CONNECTION

    def test_classify_requests_http_error(self) -> None:
        """Test classifying requests.HTTPError."""
        mock_response = type("Response", (), {"status_code": 404})()
        exception = requests.HTTPError("Not found")
        exception.response = mock_response

        classified = classify_error(exception, endpoint="/api/test")

        assert isinstance(classified, HTTPError)
        assert classified.status_code == 404
        assert classified.error_code == ErrorCode.HTTP_NOT_FOUND

    def test_classify_generic_exception(self) -> None:
        """Test classifying a generic exception."""
        exception = ValueError("Invalid value")
        classified = classify_error(exception, endpoint="/api/test")

        assert isinstance(classified, APIError)
        assert classified.error_code == ErrorCode.UNKNOWN_ERROR
        assert classified.details["exception_type"] == "ValueError"


class TestIsRetryable:
    """Test suite for is_retryable function."""

    def test_is_retryable_with_api_error(self) -> None:
        """Test is_retryable with APIError."""
        retryable_error = NetworkError(message="Network issue")
        non_retryable_error = AuthenticationError(message="Auth failed")

        assert is_retryable(retryable_error) is True
        assert is_retryable(non_retryable_error) is False

    def test_is_retryable_with_generic_exception(self) -> None:
        """Test is_retryable with generic exception."""
        timeout = requests.Timeout("Timeout")
        value_error = ValueError("Invalid")

        assert is_retryable(timeout) is True
        assert is_retryable(value_error) is False


class TestGetRetryDelay:
    """Test suite for get_retry_delay function."""

    def test_get_retry_delay_exponential_backoff(self) -> None:
        """Test exponential backoff calculation."""
        error = NetworkError(message="Network issue")

        assert get_retry_delay(error, attempt=0) == 1
        assert get_retry_delay(error, attempt=1) == 2
        assert get_retry_delay(error, attempt=2) == 4
        assert get_retry_delay(error, attempt=3) == 8

    def test_get_retry_delay_max_cap(self) -> None:
        """Test retry delay is capped at 60 seconds."""
        error = NetworkError(message="Network issue")

        assert get_retry_delay(error, attempt=10) == 60

    def test_get_retry_delay_with_rate_limit(self) -> None:
        """Test retry delay uses retry_after from RateLimitError."""
        error = RateLimitError(message="Rate limited", retry_after=120)

        assert get_retry_delay(error, attempt=0) == 120.0

    def test_get_retry_delay_rate_limit_without_retry_after(self) -> None:
        """Test retry delay with RateLimitError without retry_after."""
        error = RateLimitError(message="Rate limited")

        # Should fall back to exponential backoff
        assert get_retry_delay(error, attempt=0) == 1
