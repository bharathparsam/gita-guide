from __future__ import annotations

import argparse
import json
from uuid import uuid4

from dotenv import load_dotenv

from app.api.service import build_phase_one_service
from app.observability.logging import configure_logging
from app.services.generation_service import AnswerHelpfulnessError


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one live grounded-guidance check")
    parser.add_argument(
        "--message",
        default=(
            "I did my best in an interview, but I am anxious because I cannot "
            "control the result."
        ),
    )
    args = parser.parse_args()
    load_dotenv(".env")
    configure_logging()
    request_id = str(uuid4())
    service = build_phase_one_service()
    try:
        try:
            response = service.guide(
                args.message,
                request_id=request_id,
                idempotency_key=f"grounded-smoke-{request_id}",
            )
        except AnswerHelpfulnessError as exc:
            validation = exc.validation
            print(
                json.dumps(
                    {
                        "status": "curated_fallback_required",
                        "request_id": request_id,
                        "fallback_trait": exc.trait_id,
                        "failed_dimensions": list(validation.failed_dimensions),
                        "quality_probabilities": {
                            "faithfulness": validation.faithfulness_probability,
                            "citation_coverage": validation.citation_coverage_probability,
                            "helpfulness": validation.helpfulness_probability,
                            "agency": validation.agency_probability,
                        },
                    },
                    indent=2,
                )
            )
            return 0
    finally:
        service.close()
    print(
        json.dumps(
            {
                "status": "ok",
                "request_id": request_id,
                "model": response.model,
                "provider_request_id": response.provider_request_id,
                "langchain_run_id": response.langchain_run_id,
                "citations": response.citations,
                "grounded_chunk_ids": response.grounded_chunk_ids,
                "validation_model": response.validation_model,
                "validation_provider_request_id": response.validation_provider_request_id,
                "quality_probabilities": {
                    "faithfulness": response.faithfulness_probability,
                    "citation_coverage": response.citation_coverage_probability,
                    "helpfulness": response.helpfulness_probability,
                    "agency": response.agency_probability,
                },
                "guidance": response.guidance,
                "presentation": response.presentation.model_dump(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
