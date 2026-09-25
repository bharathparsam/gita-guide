from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableLambda

from app.models.classification import ClassificationResult


class RetrievalCorpusError(RuntimeError):
    """Raised when retrieval artifacts fail their provenance contract."""


class QueryEmbeddings(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class GitaRetriever(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        minimum_score: float = -1.0,
    ) -> list[Document]: ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_classification_query(
    message: str,
    classification: ClassificationResult,
) -> str:
    """Create an auditable query from the message and Phase 1 decision."""
    return (
        f"User situation: {message.strip()}\n"
        f"Primary situation: {classification.primary_situation}\n"
        f"Primary emotion: {classification.primary_emotion}\n"
        f"Root conflict: {classification.root_conflict}"
    )


class GitaVectorRetriever:
    """In-process cosine retriever over the provenance-checked Gita artifacts."""

    def __init__(
        self,
        *,
        chunks: list[dict[str, Any]],
        vectors: np.ndarray,
        embeddings: QueryEmbeddings,
        model_name: str,
        query_prefix: str = "query: ",
    ) -> None:
        if not chunks:
            raise RetrievalCorpusError("Gita chunk corpus is empty")
        if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
            raise RetrievalCorpusError("Embedding rows do not match Gita chunks")
        self._chunks = chunks
        self._vectors = vectors.astype(np.float32, copy=False)
        self._embeddings = embeddings
        self.model_name = model_name
        self.query_prefix = query_prefix

    @classmethod
    def from_files(
        cls,
        *,
        chunks_path: Path,
        embeddings_path: Path,
        metadata_path: Path,
        embeddings: QueryEmbeddings,
    ) -> GitaVectorRetriever:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        chunks = [
            json.loads(line)
            for line in chunks_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        vectors = np.load(embeddings_path, allow_pickle=False, mmap_mode="r")

        if metadata.get("chunks_sha256") != _sha256(chunks_path):
            raise RetrievalCorpusError("Chunk checksum does not match embedding metadata")
        if metadata.get("rows") != len(chunks):
            raise RetrievalCorpusError("Chunk count does not match embedding metadata")
        if metadata.get("dimensions") != vectors.shape[1]:
            raise RetrievalCorpusError("Embedding dimensions do not match metadata")
        if metadata.get("embeddings_sha256") != _sha256(embeddings_path):
            raise RetrievalCorpusError("Embedding checksum does not match metadata")
        if metadata.get("normalized") is not True:
            raise RetrievalCorpusError("Stored embeddings must be normalized")

        return cls(
            chunks=chunks,
            vectors=vectors,
            embeddings=embeddings,
            model_name=str(metadata["model"]),
            query_prefix=str(metadata.get("query_prefix", "query: ")),
        )

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        minimum_score: float = -1.0,
    ) -> list[Document]:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        query_vector = np.asarray(
            self._embeddings.embed_query(f"{self.query_prefix}{query.strip()}"),
            dtype=np.float32,
        )
        if query_vector.ndim != 1 or query_vector.shape[0] != self._vectors.shape[1]:
            raise RetrievalCorpusError("Query embedding dimensions do not match corpus")
        norm = float(np.linalg.norm(query_vector))
        if norm == 0:
            raise RetrievalCorpusError("Query embedding cannot be a zero vector")
        query_vector /= norm
        scores = self._vectors @ query_vector
        ranked_indices = np.argsort(-scores, kind="stable")[:top_k]

        documents: list[Document] = []
        for index in ranked_indices:
            score = float(scores[index])
            if score < minimum_score:
                continue
            chunk = self._chunks[int(index)]
            metadata = {
                key: chunk[key]
                for key in (
                    "chunk_id",
                    "source_id",
                    "chapter",
                    "chapter_title",
                    "verse_start",
                    "verse_end",
                    "verse_label",
                    "speaker",
                    "source_pdf_page",
                )
                if key in chunk
            }
            metadata.update(
                {
                    "similarity_score": score,
                    "embedding_model": self.model_name,
                }
            )
            documents.append(
                Document(
                    page_content=str(chunk["translation"]),
                    metadata=metadata,
                )
            )
        return documents


def build_retrieval_chain(
    retriever: GitaRetriever,
    *,
    top_k: int = 5,
    minimum_score: float = -1.0,
) -> Runnable[dict[str, Any], dict[str, Any]]:
    """Create the independently traceable LangChain retrieval stage."""

    def retrieve_chunks(state: dict[str, Any]) -> dict[str, Any]:
        classification = ClassificationResult.model_validate(state["classification"])
        query = build_classification_query(state["message"], classification)
        documents = retriever.retrieve(
            query,
            top_k=top_k,
            minimum_score=minimum_score,
        )
        return {**state, "retrieval_query": query, "documents": documents}

    return cast(
        Runnable[dict[str, Any], dict[str, Any]],
        RunnableLambda(retrieve_chunks).with_config(
            run_name="retrieve_gita_chunks",
            tags=["phase-2", "retrieval"],
        ),
    )
