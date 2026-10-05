from __future__ import annotations

from app.models.classification import ClassificationResult, GitaTrait


# Curated from the same trait-to-verse catalog used by the offline experience. An
# anchor is only guaranteed consideration: it must still pass JEV retrieval
# validation before it can reach generation.
TRAIT_VERSE_ANCHORS: dict[GitaTrait, str] = {
    "anxiety": "12.15",
    "fear": "2.56",
    "worry": "12.15",
    "grief": "2.14",
    "sadness": "2.14",
    "distress": "2.56",
    "moroseness": "18.35",
    "overthinking": "6.6",
    "restless_mind": "6.35",
    "distraction": "6.26",
    "confusion": "2.63",
    "doubt": "4.40",
    "indecision": "18.63",
    "self_doubt": "6.5",
    "anger": "2.62",
    "frustration": "2.62",
    "lust": "3.39",
    "greed": "16.21",
    "attachment": "2.62",
    "obsession": "2.62",
    "temptation": "3.41",
    "addictive_desire": "3.39",
    "fear_of_failure": "2.47",
    "failure": "2.48",
    "success": "2.48",
    "result_obsession": "2.47",
    "performance_pressure": "2.48",
    "procrastination": "2.47",
    "career_comparison": "18.47",
    "purpose": "18.46",
    "motivation": "18.26",
    "discipline": "18.33",
    "laziness": "18.35",
    "oversleeping": "6.16",
    "poor_routine": "6.17",
    "lack_of_self_control": "6.6",
    "impulsiveness": "3.41",
    "extreme_behaviour": "6.16",
    "jealousy": "12.13",
    "envy": "12.13",
    "hatred": "12.13",
    "resentment": "12.13",
    "forgiveness": "16.3",
    "conflict": "12.18",
    "insult": "12.18",
    "criticism": "12.19",
    "need_for_approval": "16.3",
    "harsh_speech": "17.15",
    "compassion": "12.13",
    "pride": "16.4",
    "arrogance": "16.4",
    "ego": "12.13",
    "need_for_recognition": "17.18",
    "show_off": "17.18",
    "humility": "13.8",
    "calmness": "6.7",
    "equanimity": "2.48",
    "contentment": "12.14",
    "patience": "2.14",
    "tolerance": "2.14",
    "courage": "16.1",
    "fearlessness": "16.1",
    "determination": "18.33",
    "fortitude": "16.3",
    "serenity": "17.16",
    "truthfulness": "16.2",
    "gentleness": "16.2",
    "nonviolence": "16.2",
    "money_obsession": "2.71",
    "covetousness": "16.2",
    "fear_of_loss": "12.17",
    "material_comparison": "6.8",
    "loss": "12.17",
    "unexpected_change": "2.14",
    "pain": "2.56",
    "rejection": "12.19",
    "uncertainty": "2.47",
    "feeling_stuck": "6.5",
}

_SITUATION_TRAIT_FALLBACKS: dict[str, GitaTrait] = {
    "fear_of_failure": "fear_of_failure",
    "outcome_anxiety": "result_obsession",
    "comparison": "career_comparison",
    "anger": "anger",
    "grief": "grief",
    "confusion": "indecision",
    "lack_of_motivation": "motivation",
    "purpose": "purpose",
    "discipline": "discipline",
    "relationship_conflict": "conflict",
    "other": "uncertainty",
}

# Some situations need more than a trait-level anchor to give the validator a
# concrete, usable choice. Relationship conflict is the clearest example: the
# general conflict verse is relevant, but passages about kindness and speech
# are often more directly groundable for an argument with someone close.
SITUATION_VERSE_ANCHORS: dict[str, tuple[str, ...]] = {
    "relationship_conflict": ("12.13", "17.15"),
}


def curated_anchor_verse_labels(
    classification: ClassificationResult,
) -> tuple[str, ...]:
    """Return curated verse labels to resolve against the active corpus."""
    trait = classification.primary_trait or _SITUATION_TRAIT_FALLBACKS[
        classification.primary_situation
    ]
    labels = (
        TRAIT_VERSE_ANCHORS[trait],
        *SITUATION_VERSE_ANCHORS.get(classification.primary_situation, ()),
    )
    return tuple(dict.fromkeys(labels))
