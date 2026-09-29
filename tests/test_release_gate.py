from pathlib import Path

from evals.check_release_gates import _check, _dataset_integrity_check, _sha256


def test_release_gate_thresholds_are_fail_closed() -> None:
    assert _check("quality", 0.8, ">=", 0.8)["passed"] is True
    assert _check("quality", 0.79, ">=", 0.8)["passed"] is False
    assert _check("errors", 0.0, "<=", 0.0)["passed"] is True
    assert _check("errors", None, ">=", 0.8)["passed"] is False


def test_release_gate_rejects_stale_dataset_report(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text("version-one", encoding="utf-8")
    report = {"dataset": {"path": str(dataset), "sha256": _sha256(dataset)}}
    assert _dataset_integrity_check("answers", report)["passed"] is True

    dataset.write_text("version-two", encoding="utf-8")
    assert _dataset_integrity_check("answers", report)["passed"] is False
