from pathlib import Path

from app.guardrails.input_safety import LexicalInputGuardrail, InputSafetyAction
from evals.quality import load_dataset


def test_adversarial_dataset_is_versioned_and_has_required_categories() -> None:
    document = load_dataset(Path("evals/adversarial_cases.json"), kind="adversarial")
    tags = {tag for case in document["cases"] for tag in case["tags"]}
    assert {"explicit", "crisis", "prompt-injection", "citation"}.issubset(tags)


def test_local_guardrail_blocks_obfuscated_explicit_language() -> None:
    guardrail = LexicalInputGuardrail()
    assert guardrail.check("f.u.c.k this").action is InputSafetyAction.BLOCK
    assert guardrail.check("f u c k this").action is InputSafetyAction.BLOCK


def test_local_guardrail_separates_crisis_from_ordinary_grief() -> None:
    guardrail = LexicalInputGuardrail()
    assert guardrail.check("I want to end my life").action is InputSafetyAction.ESCALATE
    assert guardrail.check("I am grieving my father's death").action is InputSafetyAction.ALLOW
