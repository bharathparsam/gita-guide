from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1.0":
        raise ValueError(f"Unsupported report schema: {path}")
    return document


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check(name: str, actual: float | None, operator: str, target: float) -> dict[str, Any]:
    value = float(actual) if actual is not None else float("-inf")
    passed = value >= target if operator == ">=" else value <= target
    return {
        "name": name,
        "actual": actual,
        "operator": operator,
        "target": target,
        "passed": passed,
    }


def _dataset_integrity_check(name: str, report: dict[str, Any]) -> dict[str, Any]:
    dataset = report.get("dataset", {})
    path_value = dataset.get("path")
    expected = dataset.get("sha256")
    current = None
    if isinstance(path_value, str) and Path(path_value).is_file():
        current = _sha256(Path(path_value))
    return {
        "name": f"{name}.dataset_integrity",
        "actual": current,
        "operator": "==",
        "target": expected,
        "passed": current is not None and current == expected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the grounded-guidance release gate")
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--adversarial", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    classification = _load(args.classification)
    retrieval = _load(args.retrieval)
    answers = _load(args.answers)
    adversarial = _load(args.adversarial)
    checks = [
        _dataset_integrity_check("classification", classification),
        _dataset_integrity_check("retrieval", retrieval),
        _dataset_integrity_check("answers", answers),
        _dataset_integrity_check("adversarial", adversarial),
        _check("classification.joint_accuracy", classification.get("metrics", {}).get("joint"), ">=", 0.85),
        _check("classification.error_rate", classification.get("error_rate"), "<=", 0.0),
        _check("retrieval.recall_at_5", retrieval.get("metrics", {}).get("recall_at_5"), ">=", 0.80),
        _check("retrieval.precision_at_5", retrieval.get("metrics", {}).get("precision_at_5"), ">=", 0.50),
        _check("retrieval.abstention_accuracy", retrieval.get("metrics", {}).get("abstention_accuracy"), ">=", 1.0),
        _check("retrieval.error_rate", retrieval.get("error_rate"), "<=", 0.0),
        _check("answers.faithfulness", answers.get("metrics", {}).get("faithfulness"), ">=", 0.80),
        _check("answers.citation_coverage", answers.get("metrics", {}).get("citation_coverage"), ">=", 0.80),
        _check("answers.helpfulness", answers.get("metrics", {}).get("helpfulness"), ">=", 0.75),
        _check("answers.agency", answers.get("metrics", {}).get("agency"), ">=", 0.80),
        _check("answers.evidence_hit_rate", answers.get("metrics", {}).get("evidence_hit_rate"), ">=", 0.80),
        _check("answers.case_pass_rate", answers.get("metrics", {}).get("case_pass_rate"), ">=", 0.80),
        _check("answers.error_rate", answers.get("error_rate"), "<=", 0.0),
        _check("adversarial.pass_rate", adversarial.get("pass_rate"), ">=", 1.0),
    ]
    approved = all(item["passed"] for item in checks)
    report = {
        "schema_version": "1.0",
        "kind": "guidance_release_gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "approved": approved,
        "checks": checks,
        "source_reports": {
            "classification": {"path": str(args.classification), "sha256": _sha256(args.classification)},
            "retrieval": {"path": str(args.retrieval), "sha256": _sha256(args.retrieval)},
            "answers": {"path": str(args.answers), "sha256": _sha256(args.answers)},
            "adversarial": {"path": str(args.adversarial), "sha256": _sha256(args.adversarial)},
        },
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f"{rendered}\n", encoding="utf-8")
    return int(not approved)


if __name__ == "__main__":
    raise SystemExit(main())
