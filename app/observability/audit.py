"""Durable, framework-independent audit records.

LangSmith is useful for model traces; it is not the authoritative audit store.
Audit events are intentionally small, versioned, and append-only.  Callers
should store identifiers, versions, fingerprints, and decisions here--never
raw prompts, responses, credentials, or authorization headers.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol


AUDIT_SCHEMA_VERSION = "1"
MAX_RECORD_BYTES = 64 * 1024
_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_SENSITIVE_FIELD_PARTS = frozenset(
    {
        "api_key",
        "authorization",
        "content",
        "credential",
        "input",
        "message",
        "output",
        "password",
        "prompt",
        "response",
        "secret",
        "token",
    }
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Audit timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _validate_metadata(value: Any, *, path: str = "metadata") -> None:
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain finite numbers")
        return
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                raise TypeError(f"{path} keys must be strings")
            normalized = raw_key.strip().lower()
            is_credential = normalized.endswith(
                ("_api_key", "_authorization", "_credential", "_password", "_secret", "_token")
            )
            if normalized in _SENSITIVE_FIELD_PARTS or is_credential:
                raise ValueError(f"Sensitive field {path}.{raw_key} is not audit-safe")
            _validate_metadata(child, path=f"{path}.{raw_key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_metadata(child, path=f"{path}[{index}]")
        return
    raise TypeError(f"{path} contains unsupported value type {type(value).__name__}")


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(child) for child in value)
    return value


def _copy_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy_json(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_json(child) for child in value]
    return value


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One immutable decision or lifecycle record."""

    event_type: str
    request_id: str
    outcome: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    occurred_at: datetime = field(default_factory=utc_now)
    schema_version: str = AUDIT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not _EVENT_TYPE_PATTERN.fullmatch(self.event_type):
            raise ValueError("event_type must be a lowercase dotted identifier")
        if not self.request_id.strip():
            raise ValueError("request_id cannot be empty")
        if not self.outcome.strip():
            raise ValueError("outcome cannot be empty")
        _isoformat_utc(self.occurred_at)
        _validate_metadata(self.metadata)
        object.__setattr__(self, "metadata", _freeze_json(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "occurred_at": _isoformat_utc(self.occurred_at),
            "event_type": self.event_type,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "outcome": self.outcome,
            "metadata": _copy_json(self.metadata),
        }


class AuditSink(Protocol):
    """Persistence boundary used by application services."""

    def record(self, event: AuditEvent) -> None: ...


class NoOpAuditSink:
    def record(self, event: AuditEvent) -> None:
        del event


class InMemoryAuditSink:
    """Thread-safe audit sink for unit tests and local assertions."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def record(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)


class JsonlAuditSink:
    """Append audit events as one JSON object per line.

    Each record is emitted in one ``O_APPEND`` write and can optionally be
    fsynced before returning.  File permissions default to owner-only.  This is
    suitable for a local durable sink or an agent-tailed file; production can
    supply another ``AuditSink`` backed by an immutable datastore.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        fsync: bool = True,
        create_parents: bool = False,
    ) -> None:
        self._path = Path(path)
        self._fsync = fsync
        self._lock = threading.Lock()
        if create_parents:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, event: AuditEvent) -> None:
        encoded = (
            json.dumps(
                event.as_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        if len(encoded) > MAX_RECORD_BYTES:
            raise ValueError(f"Audit record exceeds {MAX_RECORD_BYTES} bytes")

        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        with self._lock:
            descriptor = os.open(self._path, flags, 0o600)
            try:
                os.fchmod(descriptor, 0o600)
                written = os.write(descriptor, encoded)
                if written != len(encoded):
                    raise OSError(
                        f"Incomplete audit write: expected {len(encoded)}, wrote {written}"
                    )
                if self._fsync:
                    os.fsync(descriptor)
            finally:
                os.close(descriptor)
