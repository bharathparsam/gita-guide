from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar


T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a provider circuit is open and calls are temporarily rejected."""


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe failure-count circuit breaker using a monotonic clock."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be greater than zero")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open_call_in_progress = False

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    def before_call(self) -> None:
        with self._lock:
            if self._state is CircuitState.CLOSED:
                return
            if self._state is CircuitState.OPEN:
                assert self._opened_at is not None
                if self._clock() - self._opened_at < self.recovery_seconds:
                    raise CircuitBreakerOpenError("provider circuit is open")
                self._state = CircuitState.HALF_OPEN
            if self._half_open_call_in_progress:
                raise CircuitBreakerOpenError("provider circuit is testing recovery")
            self._half_open_call_in_progress = True

    def record_success(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._opened_at = None
            self._half_open_call_in_progress = False

    def record_failure(self) -> None:
        with self._lock:
            self._half_open_call_in_progress = False
            self._failures += 1
            if (
                self._state is CircuitState.HALF_OPEN
                or self._failures >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    base_delay_seconds: float = 0.2
    max_delay_seconds: float = 2.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")

    def delay_for_attempt(self, attempt: int, *, random_value: float | None = None) -> float:
        base = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (2 ** max(0, attempt - 1)),
        )
        jitter = base * self.jitter_ratio
        sample = random.random() if random_value is None else random_value
        return max(0.0, base - jitter + (2 * jitter * sample))


def call_with_resilience(
    operation: Callable[[], T],
    *,
    retry_on: tuple[type[BaseException], ...],
    retry_policy: RetryPolicy,
    circuit_breaker: CircuitBreaker,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Execute a provider operation with bounded retry and a circuit breaker."""
    circuit_breaker.before_call()
    for attempt in range(1, retry_policy.max_attempts + 1):
        try:
            result = operation()
        except retry_on:
            if attempt == retry_policy.max_attempts:
                circuit_breaker.record_failure()
                raise
            sleep(retry_policy.delay_for_attempt(attempt))
        except BaseException:
            circuit_breaker.record_failure()
            raise
        else:
            circuit_breaker.record_success()
            return result
    raise AssertionError("unreachable")
