from pathlib import Path

from app.classifiers.taxonomy import EMOTIONS, ROOT_CONFLICTS, SITUATIONS
from evals.run_classification_evals import load_cases


def test_evaluation_cases_have_unique_ids_and_valid_labels() -> None:
    cases = load_cases(Path("evals/classification_cases.json"))
    ids = [case["id"] for case in cases]

    assert len(ids) == len(set(ids))
    assert len(cases) >= 20

    allowed = {
        "primary_situation": SITUATIONS,
        "primary_emotion": EMOTIONS,
        "root_conflict": ROOT_CONFLICTS,
    }
    for case in cases:
        assert case["message"].strip()
        expected = case["expected"]
        assert isinstance(expected["in_scope"], bool)
        for field, taxonomy in allowed.items():
            if field in expected:
                assert expected[field]
                assert set(expected[field]).issubset(taxonomy)
