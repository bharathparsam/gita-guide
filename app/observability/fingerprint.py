"""Privacy-preserving fingerprints for prompts and other sensitive text.

Plain SHA-256 hashes of user text are vulnerable to dictionary attacks.  This
module uses a deployment secret as an HMAC key so logs can correlate identical
prompts without making common messages guessable.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any


FINGERPRINT_ALGORITHM = "hmac-sha256-v1"
MINIMUM_SECRET_BYTES = 32


def canonicalize_prompt(prompt: Any) -> str:
    """Return the stable representation used to fingerprint a prompt."""
    if isinstance(prompt, str):
        return prompt
    return json.dumps(
        prompt,
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class PromptFingerprint:
    """A log-safe prompt identity with explicit key-rotation metadata."""

    digest: str
    key_id: str
    characters: int
    algorithm: str = FINGERPRINT_ALGORITHM

    def as_log_fields(self) -> dict[str, str | int]:
        return {
            "prompt_fingerprint": self.digest,
            "prompt_fingerprint_algorithm": self.algorithm,
            "prompt_fingerprint_key_id": self.key_id,
            "prompt_characters": self.characters,
        }


class PromptFingerprinter:
    """Create deterministic, keyed prompt fingerprints.

    ``key_id`` is deliberately logged alongside the digest so the key can be
    rotated without losing the ability to interpret older audit records.  The
    key itself is never retained in log fields or object representations.
    """

    def __init__(self, secret: bytes, *, key_id: str) -> None:
        if len(secret) < MINIMUM_SECRET_BYTES:
            raise ValueError(
                f"Fingerprint secret must be at least {MINIMUM_SECRET_BYTES} bytes"
            )
        if not key_id.strip():
            raise ValueError("Fingerprint key_id cannot be empty")
        self._secret = bytes(secret)
        self._key_id = key_id.strip()

    def __repr__(self) -> str:
        return f"PromptFingerprinter(key_id={self._key_id!r}, secret=<redacted>)"

    def fingerprint(self, prompt: Any) -> PromptFingerprint:
        canonical = canonicalize_prompt(prompt)
        digest = hmac.new(
            self._secret,
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return PromptFingerprint(
            digest=digest,
            key_id=self._key_id,
            characters=len(canonical),
        )

