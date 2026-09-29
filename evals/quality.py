from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_dataset(path: Path, *, kind: str) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1.0":
        raise ValueError("Unsupported evaluation schema version")
    if document.get("kind") != kind:
        raise ValueError(f"Expected {kind!r} evaluation dataset")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation dataset must contain cases")
    identifiers = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(identifiers) != len(cases) or len(set(identifiers)) != len(cases):
        raise ValueError("Evaluation case IDs must be present and unique")
    return document


def dataset_identity(path: Path) -> dict[str, str]:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def score_retrieval_case(
    case: dict[str, Any],
    retrieved_chunk_ids: list[str],
    *,
    abstained: bool,
) -> dict[str, Any]:
    expected_abstention = bool(case.get("expect_abstention", False))
    if expected_abstention:
        return {
            "passed": abstained or not retrieved_chunk_ids,
            "precision_at_5": None,
            "recall_at_5": None,
            "hit_count": 0,
            "expected_abstention": True,
        }

    relevant = set(case["relevant_chunk_ids"])
    minimum_hits = int(case.get("minimum_relevant_hits", 1))
    returned = retrieved_chunk_ids[:5]
    hits = relevant.intersection(returned)
    precision = len(hits) / len(returned) if returned else 0.0
    recall = min(1.0, len(hits) / minimum_hits)
    forbidden = set(case.get("forbidden_chunk_ids", ())).intersection(returned)
    return {
        "passed": len(hits) >= minimum_hits and not forbidden,
        "precision_at_5": round(precision, 4),
        "recall_at_5": round(recall, 4),
        "hit_count": len(hits),
        "expected_abstention": False,
        "forbidden_hits": sorted(forbidden),
    }
