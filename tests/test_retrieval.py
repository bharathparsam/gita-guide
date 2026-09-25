import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from app.models.classification import ClassificationResult
from app.retrieval import (
    GitaVectorRetriever,
    RetrievalCorpusError,
    build_classification_query,
    build_retrieval_chain,
)


class FakeEmbeddings:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return self.vector


def classification() -> ClassificationResult:
    return ClassificationResult(
        in_scope=True,
        in_scope_probability=0.95,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.9,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="attachment_to_results",
        root_conflict_confidence=0.9,
    )


def artifacts(tmp_path: Path) -> tuple[Path, Path, Path]:
    chunks = [
        {
            "chunk_id": "gita:2:47",
            "source_id": "gita-test",
            "chapter": 2,
            "chapter_title": "Knowledge",
            "verse_start": 47,
            "verse_end": 47,
            "verse_label": "47",
            "speaker": "Krishna",
            "source_pdf_page": 10,
            "translation": "Act without attachment to results.",
        },
        {
            "chunk_id": "gita:6:5",
            "source_id": "gita-test",
            "chapter": 6,
            "chapter_title": "Meditation",
            "verse_start": 5,
            "verse_end": 5,
            "verse_label": "5",
            "speaker": "Krishna",
            "source_pdf_page": 30,
            "translation": "Lift yourself through disciplined thought.",
        },
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(
        "".join(json.dumps(chunk) + "\n" for chunk in chunks), encoding="utf-8"
    )
    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    embeddings_path = tmp_path / "embeddings.npy"
    np.save(embeddings_path, vectors)
    metadata_path = tmp_path / "embeddings.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model": "test-embeddings",
                "chunks_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
                "rows": 2,
                "dimensions": 2,
                "embeddings_sha256": hashlib.sha256(
                    embeddings_path.read_bytes()
                ).hexdigest(),
                "normalized": True,
                "query_prefix": "query: ",
            }
        ),
        encoding="utf-8",
    )
    return chunks_path, embeddings_path, metadata_path


def test_retriever_ranks_chunks_and_preserves_citation_metadata(tmp_path: Path) -> None:
    chunks_path, embeddings_path, metadata_path = artifacts(tmp_path)
    embeddings = FakeEmbeddings([0.9, 0.1])
    retriever = GitaVectorRetriever.from_files(
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        metadata_path=metadata_path,
        embeddings=embeddings,
    )

    documents = retriever.retrieve("fear of results", top_k=2)

    assert documents[0].metadata["chunk_id"] == "gita:2:47"
    assert documents[0].metadata["verse_label"] == "47"
    assert documents[0].metadata["similarity_score"] > documents[1].metadata[
        "similarity_score"
    ]
    assert embeddings.queries == ["query: fear of results"]


def test_retrieval_chain_uses_phase_one_classification(tmp_path: Path) -> None:
    chunks_path, embeddings_path, metadata_path = artifacts(tmp_path)
    retriever = GitaVectorRetriever.from_files(
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        metadata_path=metadata_path,
        embeddings=FakeEmbeddings([1.0, 0.0]),
    )
    chain = build_retrieval_chain(retriever, top_k=1)

    output = chain.invoke(
        {"message": "I fear failing", "classification": classification()}
    )

    assert output["documents"][0].metadata["chapter"] == 2
    assert "Primary situation: outcome_anxiety" in output["retrieval_query"]
    assert "Root conflict: attachment_to_results" in build_classification_query(
        "I fear failing", classification()
    )


def test_retriever_rejects_artifacts_with_wrong_checksum(tmp_path: Path) -> None:
    chunks_path, embeddings_path, metadata_path = artifacts(tmp_path)
    metadata = json.loads(metadata_path.read_text())
    metadata["chunks_sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata))

    with pytest.raises(RetrievalCorpusError, match="checksum"):
        GitaVectorRetriever.from_files(
            chunks_path=chunks_path,
            embeddings_path=embeddings_path,
            metadata_path=metadata_path,
            embeddings=FakeEmbeddings([1.0, 0.0]),
        )
