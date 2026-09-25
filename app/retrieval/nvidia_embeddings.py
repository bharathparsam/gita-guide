from __future__ import annotations

import math
import os
from collections.abc import Sequence

import requests
from langchain_core.embeddings import Embeddings

from app.observability.logging import get_logger, prompt_log_fields
from app.reliability import CircuitBreaker, RetryPolicy, call_with_resilience


DEFAULT_NVIDIA_EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b"
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NEMOTRON_EMBEDDING_DIMENSIONS = 2048
logger = get_logger("nvidia_embeddings")


class NvidiaEmbeddingError(RuntimeError):
    """Raised when NVIDIA does not return a valid embedding response."""


class NvidiaNemotronEmbeddings(Embeddings):
    """LangChain embedding client for NVIDIA Nemotron 3 Embed 1B.

    The provider receives explicit ``query`` and ``passage`` input types. Text is
    never written to application logs; only its HMAC fingerprint and size are.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_NVIDIA_BASE_URL,
        model: str = DEFAULT_NVIDIA_EMBEDDING_MODEL,
        batch_size: int = 32,
        timeout_seconds: float = 60.0,
        max_attempts: int = 2,
        session: requests.Session | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("NVIDIA_API_KEY is required for embeddings")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.session = session or requests.Session()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_seconds=30,
        )

    @classmethod
    def from_environment(cls) -> NvidiaNemotronEmbeddings:
        api_key = os.getenv("NVIDIA_API_KEY", "").strip()
        return cls(
            api_key=api_key,
            base_url=os.getenv(
                "NVIDIA_EMBEDDING_URL",
                os.getenv("NVIDIA_GUARDRAIL_URL", DEFAULT_NVIDIA_BASE_URL),
            ),
            model=os.getenv(
                "NVIDIA_EMBEDDING_MODEL", DEFAULT_NVIDIA_EMBEDDING_MODEL
            ),
            batch_size=int(os.getenv("NVIDIA_EMBEDDING_BATCH_SIZE", "32")),
            timeout_seconds=float(
                os.getenv("NVIDIA_EMBEDDING_TIMEOUT_SECONDS", "60")
            ),
            max_attempts=int(os.getenv("PROVIDER_MAX_ATTEMPTS", "2")),
        )

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/embeddings"):
            return self.base_url
        return f"{self.base_url}/embeddings"

    def _embed_batch(
        self,
        texts: Sequence[str],
        *,
        input_type: str,
    ) -> list[list[float]]:
        if input_type not in {"query", "passage"}:
            raise ValueError("input_type must be query or passage")
        normalized = [text.strip() for text in texts]
        if not normalized or any(not text for text in normalized):
            raise ValueError("Embedding inputs cannot be empty")
        payload = {
            "model": self.model,
            "input": normalized,
            "input_type": input_type,
            "modality": "text",
            "encoding_format": "float",
            "truncate": "NONE",
        }
        logger.info(
            "model.prompt.prepared",
            extra={
                "stage": "embed_gita_retrieval",
                "provider": "nvidia",
                "model": self.model,
                "prompt_kind": f"embedding_{input_type}",
                "batch_size": len(normalized),
                **prompt_log_fields(payload),
            },
        )

        def send_request() -> requests.Response:
            response = self.session.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response

        try:
            response = call_with_resilience(
                send_request,
                retry_on=(requests.Timeout, requests.ConnectionError),
                retry_policy=RetryPolicy(max_attempts=self.max_attempts),
                circuit_breaker=self.circuit_breaker,
            )
            body = response.json()
            raw_data = body["data"]
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise NvidiaEmbeddingError(
                f"NVIDIA embedding request failed: {exc}"
            ) from exc
        if not isinstance(raw_data, list) or len(raw_data) != len(normalized):
            raise NvidiaEmbeddingError("NVIDIA returned the wrong embedding count")

        ordered = sorted(raw_data, key=lambda item: item.get("index", -1))
        vectors: list[list[float]] = []
        for expected_index, item in enumerate(ordered):
            if not isinstance(item, dict) or item.get("index") != expected_index:
                raise NvidiaEmbeddingError("NVIDIA returned invalid embedding indexes")
            vector = item.get("embedding")
            if not isinstance(vector, list) or len(vector) != NEMOTRON_EMBEDDING_DIMENSIONS:
                raise NvidiaEmbeddingError(
                    "NVIDIA returned an unexpected embedding dimension"
                )
            resolved = [float(value) for value in vector]
            if not all(math.isfinite(value) for value in resolved):
                raise NvidiaEmbeddingError("NVIDIA returned a non-finite embedding")
            vectors.append(resolved)
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(
                self._embed_batch(
                    texts[start : start + self.batch_size],
                    input_type="passage",
                )
            )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([text], input_type="query")[0]
