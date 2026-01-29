"""Unit tests for OpenRouter client.

Tests the OpenRouter API client including authentication,
retry logic, and response parsing.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.shared.llm.openrouter import (
    DEFAULT_MODEL,
    LLMResponse,
    OpenRouterAuthError,
    OpenRouterClient,
    OpenRouterConfig,
    OpenRouterError,
    OpenRouterRateLimitError,
    OpenRouterTimeoutError,
    create_openrouter_client,
)


class TestOpenRouterConfig:
    """Tests for OpenRouterConfig dataclass."""

    def test_config_with_defaults(self) -> None:
        """Test config with default values."""
        config = OpenRouterConfig(api_key="test-key")

        assert config.api_key == "test-key"
        assert config.model == DEFAULT_MODEL
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.max_tokens == 1024
        assert config.temperature == 0.3

    def test_config_with_custom_values(self) -> None:
        """Test config with custom values."""
        config = OpenRouterConfig(
            api_key="custom-key",
            model="anthropic/claude-3-opus",
            timeout_seconds=60.0,
            max_retries=5,
            max_tokens=2048,
            temperature=0.7,
        )

        assert config.api_key == "custom-key"
        assert config.model == "anthropic/claude-3-opus"
        assert config.timeout_seconds == 60.0
        assert config.max_retries == 5
        assert config.max_tokens == 2048
        assert config.temperature == 0.7

    def test_config_is_immutable(self) -> None:
        """Test that config is frozen (immutable)."""
        config = OpenRouterConfig(api_key="test-key")

        with pytest.raises(Exception):  # FrozenInstanceError
            config.api_key = "new-key"  # type: ignore


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_response_creation(self) -> None:
        """Test creating LLM response."""
        response = LLMResponse(
            content="Hello, world!",
            model="anthropic/claude-sonnet-4",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            finish_reason="stop",
            latency_ms=150.0,
        )

        assert response.content == "Hello, world!"
        assert response.model == "anthropic/claude-sonnet-4"
        assert response.usage["total_tokens"] == 15
        assert response.finish_reason == "stop"
        assert response.latency_ms == 150.0

    def test_response_default_values(self) -> None:
        """Test response with default values."""
        response = LLMResponse(
            content="Test",
            model="test-model",
        )

        assert response.usage == {}
        assert response.finish_reason == "stop"
        assert isinstance(response.created_at, datetime)


class TestOpenRouterClient:
    """Tests for OpenRouterClient class."""

    @pytest.fixture
    def config(self) -> OpenRouterConfig:
        """Create test config."""
        return OpenRouterConfig(api_key="test-api-key")

    @pytest.fixture
    def client(self, config: OpenRouterConfig) -> OpenRouterClient:
        """Create test client."""
        return OpenRouterClient(config)

    def test_client_initialization(self, client: OpenRouterClient) -> None:
        """Test client initialization."""
        assert client._config.api_key == "test-api-key"
        assert client._client is None  # Lazy initialization

    @patch("httpx.Client.post")
    def test_chat_success(
        self, mock_post: MagicMock, client: OpenRouterClient
    ) -> None:
        """Test successful chat completion."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "anthropic/claude-sonnet-4",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        mock_post.return_value = mock_response

        response = client.chat("Say hello")

        assert response.content == "Hello!"
        assert response.model == "anthropic/claude-sonnet-4"
        assert response.usage["total_tokens"] == 15

    @patch("httpx.Client.post")
    def test_chat_with_system_prompt(
        self, mock_post: MagicMock, client: OpenRouterClient
    ) -> None:
        """Test chat with system prompt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}, "finish_reason": "stop"}],
            "usage": {},
        }
        mock_post.return_value = mock_response

        client.chat("User message", system_prompt="You are helpful")

        # Verify request payload
        call_args = mock_post.call_args
        request_data = call_args[1]["json"]
        messages = request_data["messages"]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User message"

    @patch("httpx.Client.post")
    def test_chat_auth_error(
        self, mock_post: MagicMock, client: OpenRouterClient
    ) -> None:
        """Test authentication error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid API key"}}
        mock_post.return_value = mock_response

        with pytest.raises(OpenRouterAuthError) as exc_info:
            client.chat("Hello")

        assert "Invalid API key" in str(exc_info.value)

    @patch("httpx.Client.post")
    def test_chat_rate_limit_error(
        self, mock_post: MagicMock, client: OpenRouterClient
    ) -> None:
        """Test rate limit error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}
        mock_post.return_value = mock_response

        with pytest.raises(OpenRouterRateLimitError) as exc_info:
            client.chat("Hello")

        assert "Rate limit" in str(exc_info.value)

    @patch("httpx.Client.post")
    def test_chat_timeout_retry(
        self, mock_post: MagicMock, client: OpenRouterClient
    ) -> None:
        """Test timeout retry logic."""
        # First two calls timeout, third succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Success"}, "finish_reason": "stop"}],
            "usage": {},
        }

        mock_post.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.TimeoutException("Timeout"),
            mock_response,
        ]

        # Should succeed after retries
        with patch("time.sleep"):  # Skip actual sleep
            response = client.chat("Hello")

        assert response.content == "Success"
        assert mock_post.call_count == 3

    @patch("httpx.Client.post")
    def test_chat_all_retries_exhausted(
        self, mock_post: MagicMock, client: OpenRouterClient
    ) -> None:
        """Test when all retries are exhausted."""
        mock_post.side_effect = httpx.TimeoutException("Timeout")

        with patch("time.sleep"):  # Skip actual sleep
            with pytest.raises(OpenRouterTimeoutError):
                client.chat("Hello")

        assert mock_post.call_count == client._config.max_retries

    @patch("httpx.Client.post")
    def test_chat_api_error(
        self, mock_post: MagicMock, client: OpenRouterClient
    ) -> None:
        """Test generic API error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": {"message": "Server error"}}
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        with pytest.raises(OpenRouterError) as exc_info:
            client.chat("Hello")

        assert "500" in str(exc_info.value)

    @patch("httpx.Client.post")
    def test_chat_empty_choices(
        self, mock_post: MagicMock, client: OpenRouterClient
    ) -> None:
        """Test handling empty choices in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}
        mock_post.return_value = mock_response

        with pytest.raises(OpenRouterError) as exc_info:
            client.chat("Hello")

        assert "No choices" in str(exc_info.value)

    def test_client_context_manager(self, config: OpenRouterConfig) -> None:
        """Test client context manager."""
        with OpenRouterClient(config) as client:
            assert client._client is None  # Not initialized yet

        # After exit, client should be None
        assert client._client is None

    def test_client_close(self, client: OpenRouterClient) -> None:
        """Test client close."""
        # Force client initialization
        client._get_client()
        assert client._client is not None

        # Close client
        client.close()
        assert client._client is None


class TestCreateOpenRouterClient:
    """Tests for factory function."""

    def test_create_with_api_key(self) -> None:
        """Test creating client with explicit API key."""
        client = create_openrouter_client(api_key="test-key")

        assert isinstance(client, OpenRouterClient)
        assert client._config.api_key == "test-key"

    def test_create_from_environment(self) -> None:
        """Test creating client from environment variable."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            client = create_openrouter_client()

            assert client._config.api_key == "env-key"

    def test_create_without_key_raises(self) -> None:
        """Test that missing API key raises error."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                create_openrouter_client()

            assert "API key required" in str(exc_info.value)


class TestOpenRouterClientIntegration:
    """Integration-style tests (mocked, but test full flow)."""

    @patch("httpx.Client.post")
    def test_full_chat_flow(self, mock_post: MagicMock) -> None:
        """Test complete chat flow with all parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "model": "anthropic/claude-sonnet-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "The weather in NYC is 42°F.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 10,
                "total_tokens": 35,
            },
        }
        mock_post.return_value = mock_response

        config = OpenRouterConfig(
            api_key="test-key",
            model="anthropic/claude-sonnet-4",
            max_tokens=512,
            temperature=0.5,
        )

        with OpenRouterClient(config) as client:
            response = client.chat(
                prompt="What is the weather in NYC?",
                system_prompt="You are a weather assistant.",
                model="anthropic/claude-sonnet-4",
                max_tokens=256,
                temperature=0.3,
            )

        assert response.content == "The weather in NYC is 42°F."
        assert response.usage["total_tokens"] == 35

        # Verify request
        call_args = mock_post.call_args
        request_data = call_args[1]["json"]

        assert request_data["model"] == "anthropic/claude-sonnet-4"
        assert request_data["max_tokens"] == 256
        assert request_data["temperature"] == 0.3
        assert len(request_data["messages"]) == 2
