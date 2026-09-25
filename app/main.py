import sys
from uuid import uuid4

from app.api.service import build_phase_one_service
from app.classifiers.jev_classifier import ClassificationError
from app.guardrails.input_safety import (
    GuardrailUnavailableError,
    InputSafetyEscalation,
    InputSafetyRejection,
)
from app.observability.logging import configure_logging


def main() -> int:
    configure_logging()
    message = input("Tell me what you're going through: ")
    service = None

    try:
        service = build_phase_one_service()
        result = service.classify(message, request_id=str(uuid4()))
    except InputSafetyEscalation:
        print(
            "\nYour safety matters more than this classification. "
            "If you may act on thoughts of harming yourself, contact local emergency "
            "services or a crisis hotline now, and reach out to someone you trust."
        )
        return 2
    except InputSafetyRejection as exc:
        print(f"\nYour message cannot be processed: {exc}")
        return 2
    except (ClassificationError, GuardrailUnavailableError, ValueError) as exc:
        print(f"\nCould not classify your message: {exc}")
        return 1
    finally:
        if service is not None:
            service.close()

    print("\nClassification:")
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
