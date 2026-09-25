from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Condition, Lock
from typing import Generic, TypeVar, cast


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class SingleFlightResult(Generic[T]):
    value: T
    shared: bool


class _Call(Generic[T]):
    def __init__(self) -> None:
        self.condition = Condition()
        self.done = False
        self.value: T | None = None
        self.error: BaseException | None = None


class SingleFlight:
    """Coalesce concurrent same-key work within one application process."""

    def __init__(self) -> None:
        self._calls: dict[str, _Call[object]] = {}
        self._lock = Lock()

    def do(self, key: str, operation: Callable[[], T]) -> SingleFlightResult[T]:
        with self._lock:
            existing = self._calls.get(key)
            if existing is None:
                call: _Call[object] = _Call()
                self._calls[key] = call
                leader = True
            else:
                call = existing
                leader = False

        if not leader:
            with call.condition:
                while not call.done:
                    call.condition.wait()
                if call.error is not None:
                    raise call.error
                return SingleFlightResult(value=cast(T, call.value), shared=True)

        try:
            value = operation()
        except BaseException as exc:
            with call.condition:
                call.error = exc
                call.done = True
                call.condition.notify_all()
            raise
        else:
            with call.condition:
                call.value = value
                call.done = True
                call.condition.notify_all()
            return SingleFlightResult(value=value, shared=False)
        finally:
            with self._lock:
                self._calls.pop(key, None)
