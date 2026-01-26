"""Centralized rate limiting using token bucket algorithm.

Provides thread-safe rate limiting for API clients with configurable
limits and metrics tracking.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from src.shared.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitMetrics:
    """Metrics for rate limiter performance tracking."""

    total_requests: int = 0
    throttled_requests: int = 0
    rejected_requests: int = 0
    total_wait_time: float = 0.0

    @property
    def avg_wait_time(self) -> float:
        """Calculate average wait time per throttled request.
        
        Returns:
            Average wait time in seconds, or 0.0 if no throttled requests
        """
        if self.throttled_requests == 0:
            return 0.0
        return self.total_wait_time / self.throttled_requests

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary of metric values
        """
        return {
            "total_requests": self.total_requests,
            "throttled_requests": self.throttled_requests,
            "rejected_requests": self.rejected_requests,
            "total_wait_time": self.total_wait_time,
            "avg_wait_time": self.avg_wait_time,
        }


class TokenBucket:
    """Thread-safe token bucket rate limiter.

    Implements the token bucket algorithm for rate limiting with
    configurable capacity and refill rate.

    The bucket starts full and refills at a constant rate. Each request
    consumes one token. If no tokens are available, the request either
    waits or is rejected based on the wait parameter.
    """

    def __init__(
        self,
        rate: float,
        capacity: int | None = None,
        name: str = "default",
    ) -> None:
        """Initialize token bucket rate limiter.

        Args:
            rate: Tokens added per second (requests per second)
            capacity: Maximum tokens in bucket. If None, uses rate as capacity.
            name: Name for logging and metrics
        """
        self.rate = rate
        self.capacity = capacity if capacity is not None else int(rate)
        self.name = name

        self._tokens = float(self.capacity)
        self._last_update = time.time()
        self._lock = threading.Lock()
        self._metrics = RateLimitMetrics()

        logger.info(
            "rate_limiter_initialized",
            name=name,
            rate=rate,
            capacity=self.capacity,
        )

    def _refill(self) -> None:
        """Refill tokens based on elapsed time.

        Must be called with lock held.
        """
        now = time.time()
        elapsed = now - self._last_update

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens + tokens_to_add)
        self._last_update = now

    def acquire(self, tokens: int = 1, wait: bool = True, timeout: float | None = None) -> bool:
        """Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire
            wait: If True, wait for tokens to become available
            timeout: Maximum time to wait in seconds. None means wait forever.

        Returns:
            True if tokens acquired, False if rejected

        Raises:
            ValueError: If tokens > capacity
        """
        if tokens > self.capacity:
            raise ValueError(f"Requested {tokens} tokens exceeds capacity {self.capacity}")

        start_time = time.time()

        with self._lock:
            self._metrics.total_requests += 1

            while True:
                self._refill()

                # Check if we have enough tokens
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

                # If not waiting, reject immediately
                if not wait:
                    self._metrics.rejected_requests += 1
                    logger.debug(
                        "rate_limit_rejected",
                        name=self.name,
                        tokens_requested=tokens,
                        tokens_available=self._tokens,
                    )
                    return False

                # Calculate wait time until next token
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate

                # Check if wait time exceeds timeout
                if timeout is not None:
                    elapsed = time.time() - start_time
                    remaining_timeout = timeout - elapsed
                    
                    if wait_time > remaining_timeout:
                        self._metrics.rejected_requests += 1
                        logger.warning(
                            "rate_limit_timeout",
                            name=self.name,
                            timeout=timeout,
                            wait_time_needed=wait_time,
                            remaining_timeout=remaining_timeout,
                        )
                        return False

                # Cap wait time to avoid excessive delays
                wait_time = min(wait_time, 1.0)

                self._metrics.throttled_requests += 1
                self._metrics.total_wait_time += wait_time

                logger.debug(
                    "rate_limit_throttle",
                    name=self.name,
                    wait_seconds=wait_time,
                    tokens_needed=tokens_needed,
                )

                # Release lock while sleeping
                self._lock.release()
                try:
                    time.sleep(wait_time)
                finally:
                    self._lock.acquire()

    def get_metrics(self) -> RateLimitMetrics:
        """Get current metrics.

        Returns:
            Copy of current metrics
        """
        with self._lock:
            return RateLimitMetrics(
                total_requests=self._metrics.total_requests,
                throttled_requests=self._metrics.throttled_requests,
                rejected_requests=self._metrics.rejected_requests,
                total_wait_time=self._metrics.total_wait_time,
            )

    def reset_metrics(self) -> None:
        """Reset metrics counters."""
        with self._lock:
            self._metrics = RateLimitMetrics()
            logger.info("rate_limiter_metrics_reset", name=self.name)

    @property
    def available_tokens(self) -> float:
        """Get current number of available tokens.

        Returns:
            Number of tokens currently available
        """
        with self._lock:
            self._refill()
            return self._tokens


class RateLimiterManager:
    """Manages multiple rate limiters for different APIs.

    Provides centralized rate limiting with per-API configurations.
    """

    def __init__(self) -> None:
        """Initialize rate limiter manager."""
        self._limiters: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

        logger.info("rate_limiter_manager_initialized")

    def get_limiter(
        self,
        name: str,
        rate: float,
        capacity: int | None = None,
    ) -> TokenBucket:
        """Get or create a rate limiter.

        Args:
            name: Unique name for the limiter
            rate: Requests per second
            capacity: Maximum burst size. If None, uses rate.

        Returns:
            TokenBucket rate limiter
        """
        with self._lock:
            if name not in self._limiters:
                self._limiters[name] = TokenBucket(
                    rate=rate,
                    capacity=capacity,
                    name=name,
                )
            return self._limiters[name]

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all rate limiters.

        Returns:
            Dictionary mapping limiter names to their metrics
        """
        with self._lock:
            return {
                name: limiter.get_metrics().to_dict() for name, limiter in self._limiters.items()
            }

    def reset_all_metrics(self) -> None:
        """Reset metrics for all rate limiters."""
        with self._lock:
            for limiter in self._limiters.values():
                limiter.reset_metrics()


# Global rate limiter manager instance
_rate_limiter_manager: RateLimiterManager | None = None


def get_rate_limiter_manager() -> RateLimiterManager:
    """Get or create global rate limiter manager.

    Returns:
        RateLimiterManager singleton instance
    """
    global _rate_limiter_manager
    if _rate_limiter_manager is None:
        _rate_limiter_manager = RateLimiterManager()
    return _rate_limiter_manager
