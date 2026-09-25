from __future__ import annotations

import json
from uuid import uuid4

from dotenv import load_dotenv

from app.api.service import build_phase_one_service
from app.observability.logging import configure_logging


def main() -> int:
    load_dotenv(".env")
    configure_logging()
    request_id = str(uuid4())
    service = build_phase_one_service()
    try:
        response = service.guide(
            "I did my best in an interview, but I am anxious because I cannot control the result.",
            request_id=request_id,
            idempotency_key=f"grounded-smoke-{request_id}",
        )
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
                "guidance": response.guidance,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
