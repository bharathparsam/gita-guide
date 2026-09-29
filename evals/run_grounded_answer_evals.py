from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter
from uuid import uuid4

from app.api.service import build_phase_one_service
from app.config import get_settings
from app.observability.logging import configure_logging
from app.services.generation_service import AnswerGroundingError
from evals.quality import dataset_identity, load_dataset


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 4)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live grounded-answer evaluations")
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/grounded_answer_cases.json")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case-id", help="Run one named evaluation case")
    parser.add_argument(
        "--generation-model",
        help=(
            "Override OPENROUTER_GENERATION_MODEL for a quality/latency comparison "
            "without editing .env"
        ),
    )
    parser.add_argument("--min-faithfulness", type=float, default=0.80)
    parser.add_argument("--min-citation-coverage", type=float, default=0.80)
    parser.add_argument("--min-helpfulness", type=float, default=0.75)
    parser.add_argument("--min-agency", type=float, default=0.80)
    parser.add_argument("--min-evidence-hit-rate", type=float, default=0.80)
    parser.add_argument("--min-case-pass-rate", type=float, default=0.80)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument(
        "--max-p95-latency",
        type=float,
        help="Optional p95 end-to-end latency gate in seconds",
    )
    args = parser.parse_args()

    configure_logging()
    if args.generation_model:
        os.environ["OPENROUTER_GENERATION_MODEL"] = args.generation_model
        get_settings.cache_clear()
    settings = get_settings()
    document = load_dataset(args.dataset, kind="grounded_answer")
    cases = document["cases"]
    if args.case_id:
        cases = [case for case in cases if case["id"] == args.case_id]
        if not cases:
            parser.error(f"Unknown grounded-answer case: {args.case_id}")
    if args.limit:
        cases = cases[: args.limit]
    service = build_phase_one_service()
    results = []
    started = datetime.now(timezone.utc)
    try:
        for case in cases:
            request_started = perf_counter()
            try:
                response = service.guide(case["message"], request_id=str(uuid4()))
                expected = set(case["expected_any_chunk_ids"])
                evidence_hit = bool(expected.intersection(response.grounded_chunk_ids))
                forbidden_hits = [
                    phrase
                    for phrase in case.get("forbidden_phrases", ())
                    if phrase.casefold() in response.guidance.casefold()
                ]
                results.append(
                    {
                        "id": case["id"],
                        "passed": evidence_hit and not forbidden_hits,
                        "evidence_hit": evidence_hit,
                        "forbidden_phrase_hits": forbidden_hits,
                        "citations": list(response.citations),
                        "grounded_chunk_ids": list(response.grounded_chunk_ids),
                        "faithfulness_probability": response.faithfulness_probability,
                        "citation_coverage_probability": (
                            response.citation_coverage_probability
                        ),
                        "helpfulness_probability": response.helpfulness_probability,
                        "agency_probability": response.agency_probability,
                        "latency_seconds": round(perf_counter() - request_started, 4),
                        "error": None,
                    }
                )
            except Exception as exc:
                quality_rejection = (
                    isinstance(exc, AnswerGroundingError)
                    and exc.validation is not None
                )
                result = {
                    "id": case["id"],
                    "passed": False,
                    "evidence_hit": False,
                    "latency_seconds": round(perf_counter() - request_started, 4),
                    "error": (
                        None if quality_rejection else f"{type(exc).__name__}: {exc}"
                    ),
                    "quality_rejection": (
                        f"{type(exc).__name__}: {exc}" if quality_rejection else None
                    ),
                }
                if isinstance(exc, AnswerGroundingError) and exc.validation is not None:
                    result.update(
                        {
                            "faithfulness_probability": (
                                exc.validation.faithfulness_probability
                            ),
                            "citation_coverage_probability": (
                                exc.validation.citation_coverage_probability
                            ),
                            "helpfulness_probability": (
                                exc.validation.helpfulness_probability
                            ),
                            "agency_probability": exc.validation.agency_probability,
                            "failed_dimensions": list(
                                exc.validation.failed_dimensions
                            ),
                        }
                    )
                results.append(result)
    finally:
        service.close()

    successful = [item for item in results if item["error"] is None]
    latencies = [float(item["latency_seconds"]) for item in results]

    def average(name: str) -> float | None:
        return round(mean(item[name] for item in successful), 4) if successful else None

    report = {
        "schema_version": "1.0",
        "kind": "grounded_answer",
        "started_at": started.isoformat(),
        "generation_model": settings.openrouter_generation_model,
        "configuration": {
            "retrieval_top_k": settings.retrieval_top_k,
            "generation_max_tokens": settings.openrouter_generation_max_tokens,
            "generation_max_attempts": settings.generation_max_attempts,
        },
        "dataset": dataset_identity(args.dataset),
        "cases": len(cases),
        "error_rate": round((len(cases) - len(successful)) / len(cases), 4),
        "metrics": {
            "faithfulness": average("faithfulness_probability"),
            "citation_coverage": average("citation_coverage_probability"),
            "helpfulness": average("helpfulness_probability"),
            "agency": average("agency_probability"),
            "evidence_hit_rate": round(
                mean(float(item["evidence_hit"]) for item in results), 4
            ),
            "case_pass_rate": round(mean(float(item["passed"]) for item in results), 4),
            "latency_mean_seconds": round(mean(latencies), 4) if latencies else None,
            "latency_p50_seconds": percentile(latencies, 0.50),
            "latency_p95_seconds": percentile(latencies, 0.95),
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
        or (metrics["faithfulness"] or 0) < args.min_faithfulness
        or (metrics["citation_coverage"] or 0) < args.min_citation_coverage
        or (metrics["helpfulness"] or 0) < args.min_helpfulness
        or (metrics["agency"] or 0) < args.min_agency
        or (metrics["evidence_hit_rate"] or 0) < args.min_evidence_hit_rate
        or (metrics["case_pass_rate"] or 0) < args.min_case_pass_rate
        or (
            args.max_p95_latency is not None
            and (metrics["latency_p95_seconds"] or float("inf"))
            > args.max_p95_latency
        )
    )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
