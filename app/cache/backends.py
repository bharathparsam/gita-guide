from __future__ import annotations

from base64 import b64decode, b64encode
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """Minimal byte-oriented cache API used by higher-level stores."""

    def get(self, key: str) -> bytes | None: ...

    def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None: ...

    def set_if_absent(self, key: str, value: bytes, *, ttl_seconds: int) -> bool: ...

    def compare_and_set(
        self,
        key: str,
        expected: bytes,
        value: bytes,
        *,
        ttl_seconds: int,
    ) -> bool: ...

    def compare_and_delete(self, key: str, expected: bytes) -> bool: ...

    def delete(self, key: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class _MemoryEntry:
    value: bytes
    expires_at: float


class InMemoryCacheBackend:
    """Thread-safe TTL cache intended for local development and deterministic tests."""

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, _MemoryEntry] = {}
        self._lock = RLock()

    @staticmethod
    def _validate_ttl(ttl_seconds: int) -> None:
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or ttl_seconds <= 0
        ):
            raise ValueError("ttl_seconds must be a positive integer")

    def _active_entry(self, key: str) -> _MemoryEntry | None:
        entry = self._entries.get(key)
        if entry is not None and entry.expires_at <= self._clock():
            del self._entries[key]
            return None
        return entry

    def get(self, key: str) -> bytes | None:
        with self._lock:
            entry = self._active_entry(key)
            return None if entry is None else entry.value

    def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        self._validate_ttl(ttl_seconds)
        with self._lock:
            self._entries[key] = _MemoryEntry(
                value=bytes(value),
                expires_at=self._clock() + ttl_seconds,
            )

    def set_if_absent(self, key: str, value: bytes, *, ttl_seconds: int) -> bool:
        self._validate_ttl(ttl_seconds)
        with self._lock:
            if self._active_entry(key) is not None:
                return False
            self._entries[key] = _MemoryEntry(
                value=bytes(value),
                expires_at=self._clock() + ttl_seconds,
            )
            return True

    def compare_and_set(
        self,
        key: str,
        expected: bytes,
        value: bytes,
        *,
        ttl_seconds: int,
    ) -> bool:
        self._validate_ttl(ttl_seconds)
        with self._lock:
            entry = self._active_entry(key)
            if entry is None or entry.value != expected:
                return False
            self._entries[key] = _MemoryEntry(
                value=bytes(value),
                expires_at=self._clock() + ttl_seconds,
            )
            return True

    def compare_and_delete(self, key: str, expected: bytes) -> bool:
        with self._lock:
            entry = self._active_entry(key)
            if entry is None or entry.value != expected:
                return False
            del self._entries[key]
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._entries.pop(key, None) is not None


class RedisClient(Protocol):
    """Subset of redis-py's synchronous client accepted by RedisCacheBackend."""

    def get(self, name: str) -> bytes | str | None: ...

    def set(
        self,
        name: str,
        value: bytes,
        *,
        ex: int,
        nx: bool = False,
    ) -> object: ...

    def delete(self, *names: str) -> int: ...

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object: ...


class RedisCacheBackend:
    """Redis adapter with namespaced keys and server-enforced TTLs.

    The client is injected deliberately. Production can pass ``redis.Redis`` while
    unit tests can use a lightweight fake without importing or starting Redis.
    """

    def __init__(self, client: RedisClient, *, namespace: str = "gita-guide") -> None:
        normalized_namespace = namespace.strip().strip(":")
        if not normalized_namespace:
            raise ValueError("namespace cannot be empty")
        self._client = client
        self._namespace = normalized_namespace

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def get(self, key: str) -> bytes | None:
        value = self._client.get(self._key(key))
        if value is None:
            return None
        return value.encode("utf-8") if isinstance(value, str) else bytes(value)

    def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        InMemoryCacheBackend._validate_ttl(ttl_seconds)
        self._client.set(self._key(key), value, ex=ttl_seconds)

    def set_if_absent(self, key: str, value: bytes, *, ttl_seconds: int) -> bool:
        InMemoryCacheBackend._validate_ttl(ttl_seconds)
        result = self._client.set(self._key(key), value, ex=ttl_seconds, nx=True)
        return bool(result)

    def compare_and_set(
        self,
        key: str,
        expected: bytes,
        value: bytes,
        *,
        ttl_seconds: int,
    ) -> bool:
        InMemoryCacheBackend._validate_ttl(ttl_seconds)
        result = self._client.eval(
            """
            if redis.call('GET', KEYS[1]) == ARGV[1] then
                redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
                return 1
            end
            return 0
            """,
            1,
            self._key(key),
            expected,
            value,
            ttl_seconds,
        )
        return bool(result)

    def compare_and_delete(self, key: str, expected: bytes) -> bool:
        result = self._client.eval(
            """
            if redis.call('GET', KEYS[1]) == ARGV[1] then
                return redis.call('DEL', KEYS[1])
            end
            return 0
            """,
            1,
            self._key(key),
            expected,
        )
        return bool(result)

    def delete(self, key: str) -> bool:
        return bool(self._client.delete(self._key(key)))


class UpstashRedisClient(Protocol):
    """Subset of the synchronous ``upstash-redis`` REST client we use."""

    def get(self, key: str) -> object: ...

    def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
        nx: bool | None = None,
    ) -> object: ...

    def delete(self, *keys: str) -> object: ...

    def eval(
        self,
        script: str,
        *,
        keys: list[str] | None = None,
        args: list[str] | None = None,
    ) -> object: ...


class UpstashRedisCacheBackend:
    """Byte-oriented cache adapter for Upstash's HTTP Redis client.

    The Upstash SDK accepts scalar JSON values rather than arbitrary bytes. Values
    are therefore base64 encoded while keys remain opaque, HMAC-derived strings.
    Compare-and-set/delete operations execute atomically in Redis via Lua.
    """

    def __init__(
        self,
        client: UpstashRedisClient,
        *,
        namespace: str = "gita-guide",
    ) -> None:
        normalized_namespace = namespace.strip().strip(":")
        if not normalized_namespace:
            raise ValueError("namespace cannot be empty")
        self._client = client
        self._namespace = normalized_namespace

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    @staticmethod
    def _encode(value: bytes) -> str:
        return b64encode(value).decode("ascii")

    @staticmethod
    def _decode(value: object) -> bytes:
        if not isinstance(value, str):
            raise ValueError("Upstash cache value must be a base64 string")
        return b64decode(value, validate=True)

    def get(self, key: str) -> bytes | None:
        value = self._client.get(self._key(key))
        return None if value is None else self._decode(value)

    def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        InMemoryCacheBackend._validate_ttl(ttl_seconds)
        self._client.set(
            self._key(key),
            self._encode(value),
            ex=ttl_seconds,
        )

    def set_if_absent(self, key: str, value: bytes, *, ttl_seconds: int) -> bool:
        InMemoryCacheBackend._validate_ttl(ttl_seconds)
        result = self._client.set(
            self._key(key),
            self._encode(value),
            ex=ttl_seconds,
            nx=True,
        )
        return bool(result)

    def compare_and_set(
        self,
        key: str,
        expected: bytes,
        value: bytes,
        *,
        ttl_seconds: int,
    ) -> bool:
        InMemoryCacheBackend._validate_ttl(ttl_seconds)
        result = self._client.eval(
            """
            if redis.call('GET', KEYS[1]) == ARGV[1] then
                redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
                return 1
            end
            return 0
            """,
            keys=[self._key(key)],
            args=[self._encode(expected), self._encode(value), str(ttl_seconds)],
        )
        return bool(result)

    def compare_and_delete(self, key: str, expected: bytes) -> bool:
        result = self._client.eval(
            """
            if redis.call('GET', KEYS[1]) == ARGV[1] then
                return redis.call('DEL', KEYS[1])
            end
            return 0
            """,
            keys=[self._key(key)],
            args=[self._encode(expected)],
        )
        return bool(result)

    def delete(self, key: str) -> bool:
        return bool(self._client.delete(self._key(key)))
