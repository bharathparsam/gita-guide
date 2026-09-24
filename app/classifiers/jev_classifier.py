from typing import Any

import requests

from app.classifiers.taxonomy import EMOTIONS, ROOT_CONFLICTS, SITUATIONS
from app.config import OPENROUTER_API_KEY
from app.models.classification import ClassificationResult


OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = "typesafe/jev-1.13"


class ClassificationError(RuntimeError):
    """Raised when JEV cannot return a valid classification."""


def _choice(answers: dict[str, Any], question: str, allowed: dict[str, str]) -> str:
    answer = answers.get(question)
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ClassificationError(f"JEV returned an invalid answer for {question}")

    choice = answer.get("choice")
    if choice not in allowed:
        raise ClassificationError(f"JEV returned an unknown {question}: {choice!r}")
    return choice


def classify_with_jev(message: str) -> ClassificationResult:
    message = message.strip()
    if not message:
        raise ValueError("Message cannot be empty")

    payload = {
        "model": JEV_MODEL,
        "state": {"message": message},
        "questions": {
            "in_scope": {
                "type": "noul",
                "instructions": (
                    "Does `message` describe a personal situation, emotional struggle, "
                    "decision, relationship issue, habit, motivation problem, or question "
                    "of purpose for which reflective life guidance could be relevant?"
                ),
                "criteria": {
                    "true": "The message describes a personal concern or inner struggle.",
                    "false": "The message is unrelated, such as a greeting, factual query, or technical task.",
                },
            },
            "primary_situation": {
                "type": "choice",
                "instructions": "Classify the primary life situation described in `message`.",
                "criteria": SITUATIONS,
            },
            "primary_emotion": {
                "type": "choice",
                "instructions": "Classify the primary emotion expressed or implied in `message`.",
                "criteria": EMOTIONS,
            },
            "root_conflict": {
                "type": "choice",
                "instructions": "Classify the main underlying inner conflict in `message`.",
                "criteria": ROOT_CONFLICTS,
            },
        },
    }

    try:
        response = requests.post(
            OPENROUTER_DECISIONS_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise ClassificationError(f"OpenRouter request failed: {exc}") from exc
    except ValueError as exc:
        raise ClassificationError("OpenRouter returned invalid JSON") from exc

    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise ClassificationError("OpenRouter response did not contain answers")

    scope_answer = answers.get("in_scope")
    if not isinstance(scope_answer, dict) or scope_answer.get("type") != "noul":
        raise ClassificationError("JEV returned an invalid answer for in_scope")

    scope_probability = scope_answer.get("noul")
    if not isinstance(scope_probability, (int, float)):
        raise ClassificationError("JEV returned an invalid in_scope probability")

    return ClassificationResult(
        in_scope=scope_probability >= 0.5,
        primary_situation=_choice(answers, "primary_situation", SITUATIONS),
        primary_emotion=_choice(answers, "primary_emotion", EMOTIONS),
        root_conflict=_choice(answers, "root_conflict", ROOT_CONFLICTS),
    )
