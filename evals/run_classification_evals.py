import argparse
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.classifiers.jev_classifier import classify_with_jev
from app.classifiers.taxonomy import TAXONOMY_VERSION
from app.observability.logging import configure_logging


FIELDS = ("in_scope", "primary_situation", "primary_emotion", "root_conflict")


def load_cases(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text())
    if document.get("schema_version") != "1.0":
        raise ValueError("Unsupported evaluation schema version")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation dataset must contain a non-empty cases list")
    return cases


def accepted(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def run(cases: list[dict[str, Any]], repeats: int) -> dict[str, Any]:
    correct = defaultdict(int)
    totals = defaultdict(int)
    failures: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    latencies: list[float] = []
    models: set[str] = set()
    confidence_totals = defaultdict(float)
    review_count = 0
    auto_accepted = 0
    auto_accepted_correct = 0
    started_at = datetime.now(timezone.utc)

    for case in cases:
        for repeat in range(repeats):
            request_started = time.perf_counter()
            try:
                result = classify_with_jev(case["message"])
            except Exception as exc:  # keep the suite running and report provider failures
                errors.append(
                    {"id": case["id"], "repeat": repeat + 1, "error": str(exc)}
                )
                continue
            latencies.append(time.perf_counter() - request_started)
            if result.model:
                models.add(result.model)
            expected = case["expected"]
            result_values = result.model_dump()
            case_ok = True
            confidence_totals["in_scope"] += result.in_scope_probability
            confidence_totals["primary_situation"] += result.primary_situation_confidence
            confidence_totals["primary_emotion"] += result.primary_emotion_confidence
            confidence_totals["root_conflict"] += result.root_conflict_confidence

            for field in FIELDS:
                if field not in expected:
                    continue
                totals[field] += 1
                field_ok = accepted(expected[field], result_values[field])
                correct[field] += int(field_ok)
                case_ok = case_ok and field_ok

            totals["joint"] += 1
            correct["joint"] += int(case_ok)
            if result.needs_review:
                review_count += 1
            else:
                auto_accepted += 1
                auto_accepted_correct += int(case_ok)
            if not case_ok:
                failures.append(
                    {
                        "id": case["id"],
                        "repeat": repeat + 1,
                        "expected": expected,
                        "actual": {field: result_values[field] for field in FIELDS},
                        "confidence": {
                            "in_scope": result.in_scope_probability,
                            "primary_situation": result.primary_situation_confidence,
                            "primary_emotion": result.primary_emotion_confidence,
                            "root_conflict": result.root_conflict_confidence,
                        },
                    }
                )

    metrics = {
        field: round(correct[field] / totals[field], 4)
        for field in (*FIELDS, "joint")
        if totals[field]
    }
    successful_requests = len(latencies)
    sorted_latencies = sorted(latencies)
    p95_index = max(0, int(len(sorted_latencies) * 0.95) - 1)
    return {
        "schema_version": "1.0",
        "started_at": started_at.isoformat(),
        "duration_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3),
        "taxonomy_version": TAXONOMY_VERSION,
        "models": sorted(models),
        "cases": len(cases),
        "repeats": repeats,
        "total_requests": len(cases) * repeats,
        "successful_requests": successful_requests,
        "error_rate": round(len(errors) / (len(cases) * repeats), 4),
        "latency_seconds": {
            "mean": round(sum(latencies) / successful_requests, 4) if latencies else None,
            "p95": round(sorted_latencies[p95_index], 4) if latencies else None,
        },
        "metrics": metrics,
        "mean_confidence": {
            field: round(confidence_totals[field] / successful_requests, 4)
            for field in FIELDS
            if successful_requests
        },
        "review_rate": round(review_count / successful_requests, 4)
        if successful_requests
        else None,
        "selective_joint_accuracy": round(
            auto_accepted_correct / auto_accepted, 4
        )
        if auto_accepted
        else None,
        "auto_accepted_requests": auto_accepted,
        "failures": failures,
        "errors": errors,
    }


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Run live JEV classification evaluations")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/classification_cases.json"),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-joint-accuracy", type=float, default=0.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    cases = load_cases(args.dataset)
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        parser.error("No evaluation cases selected")
    report = run(cases, args.repeats)
    report["dataset"] = {
        "path": str(args.dataset),
        "sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n")

    accuracy_failed = report["metrics"].get("joint", 0) < args.min_joint_accuracy
    reliability_failed = report["error_rate"] > args.max_error_rate
    return int(accuracy_failed or reliability_failed)


if __name__ == "__main__":
    raise SystemExit(main())
