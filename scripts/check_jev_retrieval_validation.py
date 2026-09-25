from __future__ import annotations

import json
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.documents import Document

from app.config import get_settings
from app.observability.logging import configure_logging, request_logging_context
from app.retrieval.jev_relevance_validator import JevRetrievalValidator
from app.retrieval.local_retriever import DEFAULT_CHUNKS_PATH


_SMOKE_CHUNK_IDS = {
    "gita-swarupananda-1909:02:047-047",
    "gita-swarupananda-1909:17:023-023",
}


def _smoke_documents() -> list[Document]:
    chunks = {
        chunk["chunk_id"]: chunk
        for chunk in (
            json.loads(line)
            for line in DEFAULT_CHUNKS_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if chunk["chunk_id"] in _SMOKE_CHUNK_IDS
    }
    missing = _SMOKE_CHUNK_IDS.difference(chunks)
    if missing:
        raise RuntimeError(f"Smoke-test chunks are missing: {sorted(missing)}")
    return [
        Document(
            page_content=str(chunks[chunk_id]["translation"]),
            metadata={
                "chunk_id": chunk_id,
                "chapter": chunks[chunk_id]["chapter"],
                "verse_label": chunks[chunk_id]["verse_label"],
            },
        )
        for chunk_id in sorted(_SMOKE_CHUNK_IDS)
    ]


def main() -> int:
    load_dotenv(".env")
    configure_logging()
    settings = get_settings()
    validator = JevRetrievalValidator(
        settings,
        threshold=settings.retrieval_validation_threshold,
    )
    request_id = str(uuid4())
    with request_logging_context(request_id):
        result = validator.validate(
            (
                "User situation: I am anxious that my work will not produce the result I want.\n"
                "Primary situation: outcome anxiety\n"
                "Primary emotion: fear\n"
                "Root conflict: attachment to results"
            ),
            _smoke_documents(),
        )
    decisions = {item.chunk_id: item for item in result.chunks}
    quality_gate_passed = (
        decisions["gita-swarupananda-1909:02:047-047"].accepted
        and not decisions["gita-swarupananda-1909:17:023-023"].accepted
    )
    print(
        json.dumps(
            {
                "status": "ok" if quality_gate_passed else "quality_gate_failed",
                "request_id": request_id,
                "model": result.model,
                "provider_request_id": result.provider_request_id,
                "threshold": validator.threshold,
                "decisions": [
                    {
                        "chunk_id": item.chunk_id,
                        "relevance_probability": item.relevance_probability,
                        "accepted": item.accepted,
                    }
                    for item in result.chunks
                ],
            },
            indent=2,
        )
    )
    return 0 if quality_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
