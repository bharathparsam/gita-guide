from pathlib import Path

from app.classifiers.taxonomy import EMOTIONS, GITA_TRAITS, ROOT_CONFLICTS, SITUATIONS
from evals.run_classification_evals import load_cases


EXPECTED_GITA_TRAITS = {
    "anxiety", "fear", "worry", "grief", "sadness", "distress", "moroseness",
    "overthinking", "restless_mind", "distraction", "confusion", "doubt",
    "indecision", "self_doubt", "anger", "frustration", "lust", "greed",
    "attachment", "obsession", "temptation", "addictive_desire",
    "fear_of_failure", "failure", "success", "result_obsession",
    "performance_pressure", "procrastination", "career_comparison", "purpose",
    "motivation", "discipline", "laziness", "oversleeping", "poor_routine",
    "lack_of_self_control", "impulsiveness", "extreme_behaviour", "jealousy",
    "envy", "hatred", "resentment", "forgiveness", "conflict", "insult",
    "criticism", "need_for_approval", "harsh_speech", "compassion", "pride",
    "arrogance", "ego", "need_for_recognition", "show_off", "humility",
    "calmness", "equanimity", "contentment", "patience", "tolerance", "courage",
    "fearlessness", "determination", "fortitude", "serenity", "truthfulness",
    "gentleness", "nonviolence", "money_obsession", "covetousness",
    "fear_of_loss", "material_comparison", "loss", "unexpected_change", "pain",
    "rejection", "uncertainty", "feeling_stuck",
}


def test_gita_trait_catalog_matches_the_approved_labels() -> None:
    assert set(GITA_TRAITS) == EXPECTED_GITA_TRAITS
    assert all(description.strip() for description in GITA_TRAITS.values())


def test_evaluation_cases_have_unique_ids_and_valid_labels() -> None:
    cases = load_cases(Path("evals/classification_cases.json"))
    ids = [case["id"] for case in cases]

    assert len(ids) == len(set(ids))
    assert len(cases) >= 20

    allowed = {
        "primary_situation": SITUATIONS,
        "primary_emotion": EMOTIONS,
        "root_conflict": ROOT_CONFLICTS,
        "primary_trait": GITA_TRAITS,
    }
    for case in cases:
        assert case["message"].strip()
        expected = case["expected"]
        assert isinstance(expected["in_scope"], bool)
        for field, taxonomy in allowed.items():
            if field in expected:
                assert expected[field]
                assert set(expected[field]).issubset(taxonomy)
