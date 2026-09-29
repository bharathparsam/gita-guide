from __future__ import annotations

import requests


class TransientProviderHttpError(requests.ConnectionError):
    """A retryable provider response such as throttling or temporary overload."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"Transient provider HTTP status: {status_code}")
        self.status_code = status_code


def raise_for_provider_status(response: requests.Response) -> None:
    """Classify HTTP failures before the shared retry/circuit-breaker boundary."""
    status_code = response.status_code
    if isinstance(status_code, int) and (
        status_code == 429 or 500 <= status_code <= 599
    ):
        raise TransientProviderHttpError(status_code)
    response.raise_for_status()
