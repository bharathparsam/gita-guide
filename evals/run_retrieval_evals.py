from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter
from uuid import uuid4

from app.api.service import build_phase_one_service
from app.observability.logging import configure_logging
from app.services.retrieval_service import RetrievalNotEligible
from evals.quality import dataset_identity, load_dataset, score_retrieval_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live retrieval quality evaluations")
    parser.add_argument("--dataset", type=Path, default=Path("evals/retrieval_cases.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--min-recall-at-5", type=float, default=0.80)
    parser.add_argument("--min-precision-at-5", type=float, default=0.50)
    parser.add_argument("--min-abstention-accuracy", type=float, default=1.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    args = parser.parse_args()

    configure_logging()
    document = load_dataset(args.dataset, kind="retrieval")
    cases = document["cases"][: args.limit] if args.limit else document["cases"]
    service = build_phase_one_service()
    results = []
    errors = 0
    started = datetime.now(timezone.utc)
    try:
        for case in cases:
            request_started = perf_counter()
            ids: list[str] = []
            abstained = False
            error = None
            try:
                context = service.classify_and_retrieve(
                    case["message"],
                    request_id=str(uuid4()),
                    idempotency_key=None,
                )
                ids = [chunk.chunk_id for chunk in context.retrieval.chunks]
                abstained = not context.retrieval.ready_for_generation
            except RetrievalNotEligible:
                abstained = True
            except Exception as exc:
                errors += 1
                error = f"{type(exc).__name__}: {exc}"
            score = score_retrieval_case(case, ids, abstained=abstained)
            results.append(
                {
                    "id": case["id"],
                    "retrieved_chunk_ids": ids,
                    "abstained": abstained,
                    "latency_seconds": round(perf_counter() - request_started, 4),
                    "error": error,
                    **score,
                }
            )
    finally:
        service.close()

    evidence = [item for item in results if not item["expected_abstention"]]
    abstentions = [item for item in results if item["expected_abstention"]]
    report = {
        "schema_version": "1.0",
        "kind": "retrieval",
        "started_at": started.isoformat(),
        "dataset": dataset_identity(args.dataset),
        "cases": len(cases),
        "error_rate": round(errors / len(cases), 4),
        "metrics": {
            "recall_at_5": round(mean(item["recall_at_5"] for item in evidence), 4)
            if evidence
            else None,
            "precision_at_5": round(
                mean(item["precision_at_5"] for item in evidence), 4
            )
            if evidence
            else None,
            "abstention_accuracy": round(
                mean(float(item["passed"]) for item in abstentions), 4
            )
            if abstentions
            else None,
            "case_pass_rate": round(mean(float(item["passed"]) for item in results), 4),
        },
        "results": results,
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    metrics = report["metrics"]
    failed = (
        report["error_rate"] > args.max_error_rate
        or (metrics["recall_at_5"] or 0) < args.min_recall_at_5
        or (metrics["precision_at_5"] or 0) < args.min_precision_at_5
        or (metrics["abstention_accuracy"] or 0) < args.min_abstention_accuracy
    )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
