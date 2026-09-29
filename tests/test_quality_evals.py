from __future__ import annotations

from pathlib import Path

from evals.quality import load_dataset, score_retrieval_case
from evals.run_grounded_answer_evals import percentile


def test_quality_datasets_have_unique_versioned_cases() -> None:
    retrieval = load_dataset(Path("evals/retrieval_cases.json"), kind="retrieval")
    answers = load_dataset(
        Path("evals/grounded_answer_cases.json"), kind="grounded_answer"
    )
    assert len(retrieval["cases"]) >= 10
    assert len(answers["cases"]) >= 5


def test_retrieval_score_measures_precision_recall_and_abstention() -> None:
    case = {
        "relevant_chunk_ids": ["a", "b"],
        "minimum_relevant_hits": 2,
    }
    score = score_retrieval_case(case, ["a", "b", "noise"], abstained=False)
    assert score["passed"] is True
    assert score["recall_at_5"] == 1.0
    assert score["precision_at_5"] == 0.6667

    abstention = score_retrieval_case(
        {"expect_abstention": True}, [], abstained=True
    )
    assert abstention["passed"] is True


def test_latency_percentiles_are_deterministic_for_small_eval_sets() -> None:
    assert percentile([], 0.95) is None
    assert percentile([1.0], 0.95) == 1.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.50) == 2.5
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 3.85
