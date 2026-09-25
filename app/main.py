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
from app.retrieval.nvidia_embeddings import NvidiaEmbeddingError
from app.retrieval.jev_relevance_validator import RetrievalValidationError
from app.services.retrieval_service import RetrievalNotEligible
from app.services.generation_service import GenerationError, GenerationNotReadyError


def main() -> int:
    configure_logging()
    message = input("Tell me what you're going through: ")
    service = None

    request_id = str(uuid4())
    try:
        service = build_phase_one_service()
        response = service.guide(
            message,
            request_id=request_id,
        )
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
    except RetrievalNotEligible as exc:
        print(f"\nRetrieval was not run: {exc}")
        return 2
    except (
        ClassificationError,
        GuardrailUnavailableError,
        NvidiaEmbeddingError,
        RetrievalValidationError,
        GenerationError,
        GenerationNotReadyError,
        ValueError,
    ) as exc:
        print(f"\nCould not process your message: {exc}")
        return 1
    finally:
        if service is not None:
            service.close()

    print("\nGuidance:")
    print(response.guidance)
    print("\nCitations:")
    print(", ".join(response.citations))
    return 0


if __name__ == "__main__":
    sys.exit(main())
