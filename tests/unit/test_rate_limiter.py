"""Unit tests for rate limiter."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import pytest

from src.shared.api.rate_limiter import RateLimiterManager, TokenBucket, get_rate_limiter_manager


class TestTokenBucket:
    """Test suite for TokenBucket rate limiter."""

    def test_token_bucket_initialization(self) -> None:
        """Test TokenBucket initializes with correct parameters."""
        bucket = TokenBucket(rate=10.0, capacity=20, name="test")

        assert bucket.rate == 10.0
        assert bucket.capacity == 20
        assert bucket.name == "test"
        assert bucket.available_tokens == 20.0

    def test_token_bucket_default_capacity(self) -> None:
        """Test TokenBucket uses rate as default capacity."""
        bucket = TokenBucket(rate=5.0, name="test")

        assert bucket.capacity == 5
        assert bucket.available_tokens == 5.0

    def test_acquire_single_token(self) -> None:
        """Test acquiring a single token."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        result = bucket.acquire(tokens=1, wait=False)

        assert result is True
        assert abs(bucket.available_tokens - 9.0) < 0.01

    def test_acquire_multiple_tokens(self) -> None:
        """Test acquiring multiple tokens."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        result = bucket.acquire(tokens=5, wait=False)

        assert result is True
        assert abs(bucket.available_tokens - 5.0) < 0.01

    def test_acquire_exceeds_capacity_raises_error(self) -> None:
        """Test acquiring more tokens than capacity raises ValueError."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        with pytest.raises(ValueError, match="exceeds capacity"):
            bucket.acquire(tokens=15, wait=False)

    def test_acquire_without_wait_rejects_when_insufficient(self) -> None:
        """Test acquire without wait rejects when insufficient tokens."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        # Consume all tokens
        bucket.acquire(tokens=10, wait=False)

        # Try to acquire more without waiting
        result = bucket.acquire(tokens=1, wait=False)

        assert result is False

    def test_acquire_with_wait_succeeds(self) -> None:
        """Test acquire with wait eventually succeeds."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        # Consume all tokens
        bucket.acquire(tokens=10, wait=False)

        # Acquire with wait should succeed after refill
        start = time.time()
        result = bucket.acquire(tokens=1, wait=True)
        elapsed = time.time() - start

        assert result is True
        assert elapsed >= 0.1  # Should wait at least 0.1 seconds for 1 token at 10/sec

    def test_acquire_with_timeout_rejects(self) -> None:
        """Test acquire with timeout rejects if timeout exceeded."""
        bucket = TokenBucket(rate=1.0, capacity=1, name="test")

        # Consume all tokens
        bucket.acquire(tokens=1, wait=False)

        # Try to acquire with short timeout
        result = bucket.acquire(tokens=1, wait=True, timeout=0.01)

        assert result is False

    def test_token_refill_over_time(self) -> None:
        """Test tokens refill over time."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        # Consume all tokens
        bucket.acquire(tokens=10, wait=False)
        assert bucket.available_tokens < 0.001

        # Wait for refill
        time.sleep(0.5)

        # Should have ~5 tokens (10 tokens/sec * 0.5 sec)
        available = bucket.available_tokens
        assert 4.0 <= available <= 6.0

    def test_token_refill_caps_at_capacity(self) -> None:
        """Test token refill doesn't exceed capacity."""
        bucket = TokenBucket(rate=10.0, capacity=5, name="test")

        # Wait longer than needed to fill
        time.sleep(1.0)

        # Should cap at capacity
        assert bucket.available_tokens == 5.0

    def test_metrics_tracking(self) -> None:
        """Test metrics are tracked correctly."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        # Successful acquire
        bucket.acquire(tokens=1, wait=False)

        # Rejected acquire
        bucket.acquire(tokens=10, wait=False)

        metrics = bucket.get_metrics()
        assert metrics.total_requests == 2
        assert metrics.rejected_requests == 1
        assert metrics.throttled_requests == 0

    def test_metrics_reset(self) -> None:
        """Test metrics can be reset."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        bucket.acquire(tokens=1, wait=False)
        bucket.reset_metrics()

        metrics = bucket.get_metrics()
        assert metrics.total_requests == 0
        assert metrics.rejected_requests == 0

    def test_thread_safety(self) -> None:
        """Test token bucket is thread-safe."""
        bucket = TokenBucket(rate=100.0, capacity=100, name="test")
        num_threads = 10
        tokens_per_thread = 10

        def acquire_tokens() -> bool:
            return bucket.acquire(tokens=tokens_per_thread, wait=True, timeout=5.0)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(acquire_tokens) for _ in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        # All should succeed
        assert all(results)

        # Total tokens consumed should equal capacity
        assert bucket.available_tokens < 0.2

        metrics = bucket.get_metrics()
        assert metrics.total_requests == num_threads


class TestRateLimiterManager:
    """Test suite for RateLimiterManager."""

    def test_manager_initialization(self) -> None:
        """Test RateLimiterManager initializes correctly."""
        manager = RateLimiterManager()

        assert manager is not None
        assert manager.get_all_metrics() == {}

    def test_get_limiter_creates_new(self) -> None:
        """Test get_limiter creates new limiter if not exists."""
        manager = RateLimiterManager()

        limiter = manager.get_limiter(name="test", rate=10.0)

        assert limiter is not None
        assert limiter.name == "test"
        assert limiter.rate == 10.0

    def test_get_limiter_returns_existing(self) -> None:
        """Test get_limiter returns existing limiter."""
        manager = RateLimiterManager()

        limiter1 = manager.get_limiter(name="test", rate=10.0)
        limiter2 = manager.get_limiter(name="test", rate=20.0)  # Different rate ignored

        assert limiter1 is limiter2

    def test_get_all_metrics(self) -> None:
        """Test get_all_metrics returns metrics for all limiters."""
        manager = RateLimiterManager()

        limiter1 = manager.get_limiter(name="api1", rate=10.0)
        limiter2 = manager.get_limiter(name="api2", rate=5.0)

        limiter1.acquire(tokens=1, wait=False)
        limiter2.acquire(tokens=1, wait=False)

        metrics = manager.get_all_metrics()

        assert "api1" in metrics
        assert "api2" in metrics
        assert metrics["api1"]["total_requests"] == 1
        assert metrics["api2"]["total_requests"] == 1

    def test_reset_all_metrics(self) -> None:
        """Test reset_all_metrics resets all limiters."""
        manager = RateLimiterManager()

        limiter1 = manager.get_limiter(name="api1", rate=10.0)
        limiter2 = manager.get_limiter(name="api2", rate=5.0)

        limiter1.acquire(tokens=1, wait=False)
        limiter2.acquire(tokens=1, wait=False)

        manager.reset_all_metrics()

        metrics = manager.get_all_metrics()
        assert metrics["api1"]["total_requests"] == 0
        assert metrics["api2"]["total_requests"] == 0

    def test_get_rate_limiter_manager_singleton(self) -> None:
        """Test get_rate_limiter_manager returns singleton."""
        manager1 = get_rate_limiter_manager()
        manager2 = get_rate_limiter_manager()

        assert manager1 is manager2

    def test_metrics_to_dict(self) -> None:
        """Test metrics to_dict includes all fields."""
        bucket = TokenBucket(rate=10.0, capacity=10, name="test")

        bucket.acquire(tokens=1, wait=False)

        metrics_dict = bucket.get_metrics().to_dict()

        assert "total_requests" in metrics_dict
        assert "throttled_requests" in metrics_dict
        assert "rejected_requests" in metrics_dict
        assert "total_wait_time" in metrics_dict
        assert "avg_wait_time" in metrics_dict

    def test_metrics_avg_wait_time_calculation(self) -> None:
        """Test average wait time is calculated correctly."""
        bucket = TokenBucket(rate=2.0, capacity=2, name="test")

        # Consume all tokens
        bucket.acquire(tokens=2, wait=False)

        # Acquire with wait (should throttle)
        bucket.acquire(tokens=1, wait=True)

        metrics = bucket.get_metrics()
        assert metrics.throttled_requests == 1
        assert metrics.avg_wait_time > 0

    def test_concurrent_limiter_creation(self) -> None:
        """Test concurrent limiter creation is thread-safe."""
        manager = RateLimiterManager()
        num_threads = 10

        def create_limiter() -> TokenBucket:
            return manager.get_limiter(name="shared", rate=10.0)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_limiter) for _ in range(num_threads)]
            limiters = [future.result() for future in as_completed(futures)]

        # All should be the same instance
        assert all(limiter is limiters[0] for limiter in limiters)
