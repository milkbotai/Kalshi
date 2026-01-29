"""OpenRouter API client for LLM access.

Implements OpenAI-compatible API with OpenRouter-specific headers.
Provides retry logic, timeout handling, and structured response parsing.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from src.shared.config.logging import get_logger

logger = get_logger(__name__)

# Default model - Claude Sonnet 4.5 via OpenRouter
DEFAULT_MODEL = "anthropic/claude-sonnet-4"

# API configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class OpenRouterConfig:
    """Configuration for OpenRouter API client.

    Attributes:
        api_key: OpenRouter API key (from environment)
        model: Model identifier (default: anthropic/claude-sonnet-4)
        timeout_seconds: Request timeout
        max_retries: Maximum retry attempts
        retry_delay_seconds: Base delay between retries (exponential backoff)
        max_tokens: Maximum tokens in response
        temperature: Model temperature (0.0-2.0)
    """

    api_key: str
    model: str = DEFAULT_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS
    max_tokens: int = 1024
    temperature: float = 0.3


@dataclass
class LLMResponse:
    """Structured LLM response.

    Attributes:
        content: The generated text content
        model: Model used for generation
        usage: Token usage statistics
        finish_reason: Why generation stopped
        created_at: When response was created
        latency_ms: Response latency in milliseconds
    """

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0


class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors."""

    pass


class OpenRouterAuthError(OpenRouterError):
    """Authentication failed with OpenRouter API."""

    pass


class OpenRouterRateLimitError(OpenRouterError):
    """Rate limit exceeded on OpenRouter API."""

    pass


class OpenRouterTimeoutError(OpenRouterError):
    """Request to OpenRouter API timed out."""

    pass


class OpenRouterClient:
    """OpenRouter API client with OpenAI-compatible interface.

    Provides access to various LLM models through OpenRouter's unified API.
    Implements retry logic with exponential backoff and structured error handling.

    Example:
        config = OpenRouterConfig(api_key="your-key")
        client = OpenRouterClient(config)
        response = client.chat("What is the weather in NYC?")
        print(response.content)
    """

    def __init__(self, config: OpenRouterConfig) -> None:
        """Initialize OpenRouter client.

        Args:
            config: Client configuration including API key
        """
        self._config = config
        self._client: httpx.Client | None = None
        logger.info(
            "openrouter_client_initialized",
            model=config.model,
            timeout=config.timeout_seconds,
        )

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=OPENROUTER_BASE_URL,
                timeout=self._config.timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "HTTP-Referer": "https://milkbot.ai",
                    "X-Title": "Milkbot Weather Trading",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def chat(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            prompt: User message/prompt
            system_prompt: Optional system message
            model: Optional model override
            max_tokens: Optional max tokens override
            temperature: Optional temperature override

        Returns:
            LLMResponse with generated content

        Raises:
            OpenRouterAuthError: If authentication fails
            OpenRouterRateLimitError: If rate limit exceeded
            OpenRouterTimeoutError: If request times out
            OpenRouterError: For other API errors
        """
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return self._chat_completion(
            messages=messages,
            model=model or self._config.model,
            max_tokens=max_tokens or self._config.max_tokens,
            temperature=temperature or self._config.temperature,
        )

    def _chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Execute chat completion with retry logic.

        Args:
            messages: Chat messages
            model: Model to use
            max_tokens: Max tokens in response
            temperature: Model temperature

        Returns:
            LLMResponse with generated content
        """
        import time

        client = self._get_client()
        request_data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error: Exception | None = None
        delay = self._config.retry_delay_seconds

        for attempt in range(self._config.max_retries):
            try:
                start_time = time.time()
                response = client.post("/chat/completions", json=request_data)
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    return self._parse_response(response.json(), latency_ms)
                elif response.status_code == 401:
                    raise OpenRouterAuthError("Invalid API key")
                elif response.status_code == 429:
                    raise OpenRouterRateLimitError("Rate limit exceeded")
                else:
                    error_detail = self._extract_error(response)
                    raise OpenRouterError(
                        f"API error ({response.status_code}): {error_detail}"
                    )

            except httpx.TimeoutException as e:
                last_error = OpenRouterTimeoutError(f"Request timed out: {e}")
                logger.warning(
                    "openrouter_timeout",
                    attempt=attempt + 1,
                    max_retries=self._config.max_retries,
                )
            except httpx.RequestError as e:
                last_error = OpenRouterError(f"Request failed: {e}")
                logger.warning(
                    "openrouter_request_error",
                    attempt=attempt + 1,
                    error=str(e),
                )
            except (OpenRouterAuthError, OpenRouterRateLimitError):
                raise  # Don't retry auth or rate limit errors

            # Exponential backoff
            if attempt < self._config.max_retries - 1:
                time.sleep(delay)
                delay *= 2

        # All retries exhausted
        if last_error:
            raise last_error
        raise OpenRouterError("All retries exhausted")

    def _parse_response(self, data: dict[str, Any], latency_ms: float) -> LLMResponse:
        """Parse API response into LLMResponse.

        Args:
            data: Raw API response
            latency_ms: Request latency

        Returns:
            Parsed LLMResponse
        """
        choices = data.get("choices", [])
        if not choices:
            raise OpenRouterError("No choices in response")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=data.get("model", self._config.model),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            finish_reason=choice.get("finish_reason", "stop"),
            latency_ms=latency_ms,
        )

    def _extract_error(self, response: httpx.Response) -> str:
        """Extract error message from response.

        Args:
            response: HTTP response

        Returns:
            Error message string
        """
        try:
            data = response.json()
            error = data.get("error", {})
            if isinstance(error, dict):
                return error.get("message", str(error))
            return str(error)
        except Exception:
            return response.text or "Unknown error"

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "OpenRouterClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()


def create_openrouter_client(api_key: str | None = None) -> OpenRouterClient:
    """Factory function to create OpenRouter client.

    Args:
        api_key: Optional API key (defaults to environment variable)

    Returns:
        Configured OpenRouterClient instance

    Raises:
        ValueError: If no API key provided or found in environment
    """
    import os

    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError(
            "OpenRouter API key required. "
            "Set OPENROUTER_API_KEY environment variable or pass api_key parameter."
        )

    config = OpenRouterConfig(api_key=key)
    return OpenRouterClient(config)
