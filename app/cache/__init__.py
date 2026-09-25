"""Reusable cache primitives for classification and request idempotency."""

from app.cache.backends import (
    CacheBackend,
    InMemoryCacheBackend,
    RedisCacheBackend,
    UpstashRedisCacheBackend,
)
from app.cache.classification import (
    CachedClassification,
    ClassificationCache,
    ClassificationCachePolicy,
)
from app.cache.idempotency import (
    IdempotencyClaim,
    IdempotencyConflict,
    IdempotencyRecord,
    IdempotencyStore,
)
from app.cache.keys import (
    ClassificationCacheKeyContext,
    HmacCacheKeyBuilder,
    RetrievalCacheKeyContext,
)
from app.cache.retrieval import CachedRetrieval, CachedRetrievalItem, RetrievalCache
from app.cache.singleflight import SingleFlight, SingleFlightResult

__all__ = [
    "CacheBackend",
    "CachedClassification",
    "ClassificationCache",
    "ClassificationCacheKeyContext",
    "ClassificationCachePolicy",
    "CachedRetrieval",
    "CachedRetrievalItem",
    "HmacCacheKeyBuilder",
    "RetrievalCache",
    "RetrievalCacheKeyContext",
    "IdempotencyClaim",
    "IdempotencyConflict",
    "IdempotencyRecord",
    "IdempotencyStore",
    "InMemoryCacheBackend",
    "RedisCacheBackend",
    "UpstashRedisCacheBackend",
    "SingleFlight",
    "SingleFlightResult",
]
