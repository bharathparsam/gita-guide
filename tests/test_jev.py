"""Manual, billable integration check. This module is safe for pytest collection."""

from app.classifiers.jev_classifier import classify_with_jev
from app.observability.logging import configure_logging


def main() -> None:
    configure_logging()
    result = classify_with_jev(
        "I worked really hard but failed my interview and now I feel useless."
    )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
