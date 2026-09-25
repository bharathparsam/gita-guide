import pytest

from app.reliability.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    RetryPolicy,
    call_with_resilience,
)


def test_retry_succeeds_after_a_transient_failure() -> None:
    attempts = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary")
        return "ok"

    result = call_with_resilience(
        operation,
        retry_on=(TimeoutError,),
        retry_policy=RetryPolicy(max_attempts=2, jitter_ratio=0),
        circuit_breaker=CircuitBreaker(),
        sleep=delays.append,
    )

    assert result == "ok"
    assert attempts == 2
    assert delays == [0.2]


def test_circuit_opens_and_recovers_through_half_open() -> None:
    now = 0.0
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_seconds=10,
        clock=lambda: now,
    )

    with pytest.raises(TimeoutError):
        call_with_resilience(
            lambda: (_ for _ in ()).throw(TimeoutError("down")),
            retry_on=(TimeoutError,),
            retry_policy=RetryPolicy(max_attempts=1),
            circuit_breaker=breaker,
        )

    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitBreakerOpenError):
        breaker.before_call()

    now = 11.0
    breaker.before_call()
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED


def test_retry_policy_is_bounded() -> None:
    policy = RetryPolicy(
        max_attempts=3,
        base_delay_seconds=2,
        max_delay_seconds=3,
        jitter_ratio=0,
    )

    assert policy.delay_for_attempt(1) == 2
    assert policy.delay_for_attempt(2) == 3
    assert policy.delay_for_attempt(10) == 3
