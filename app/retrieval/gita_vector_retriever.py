from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections.abc import Iterable, Sequence
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
        source_ids: frozenset[str] | None = None,
        speakers: frozenset[str] | None = None,
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
        f"Primary situation: {classification.primary_situation.replace('_', ' ')}\n"
        f"Primary emotion: {classification.primary_emotion.replace('_', ' ')}\n"
        f"Root conflict: {classification.root_conflict.replace('_', ' ')}"
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
        corpus_sha256: str,
        query_prefix: str = "query: ",
    ) -> None:
        if not chunks:
            raise RetrievalCorpusError("Gita chunk corpus is empty")
        if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
            raise RetrievalCorpusError("Embedding rows do not match Gita chunks")
        self._chunks = chunks
        self._vectors = vectors.astype(np.float32, copy=False)
        self._embeddings = embeddings
        self._chunk_index = {
            str(chunk["chunk_id"]): index for index, chunk in enumerate(chunks)
        }
        if len(self._chunk_index) != len(chunks):
            raise RetrievalCorpusError("Gita chunk IDs must be unique")
        self.model_name = model_name
        self.corpus_sha256 = corpus_sha256
        self.query_prefix = query_prefix

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

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
            corpus_sha256=str(metadata["chunks_sha256"]),
            query_prefix=str(metadata.get("query_prefix", "query: ")),
        )

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        minimum_score: float = -1.0,
        source_ids: frozenset[str] | None = None,
        speakers: frozenset[str] | None = None,
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
        eligible_indices = np.asarray(
            [
                index
                for index, chunk in enumerate(self._chunks)
                if (source_ids is None or str(chunk.get("source_id")) in source_ids)
                and (speakers is None or str(chunk.get("speaker")) in speakers)
            ],
            dtype=np.int64,
        )
        if eligible_indices.size == 0:
            return []
        eligible_scores = scores[eligible_indices]
        ranked_positions = np.argsort(-eligible_scores, kind="stable")[:top_k]
        ranked_indices = eligible_indices[ranked_positions]

        documents: list[Document] = []
        for dense_rank, index in enumerate(ranked_indices, start=1):
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
                    "dense_rank": dense_rank,
                }
            )
            documents.append(
                Document(
                    page_content=str(chunk["translation"]),
                    metadata=metadata,
                )
            )
        return documents

    def pairwise_similarity(self, first_chunk_id: str, second_chunk_id: str) -> float:
        """Return corpus-vector similarity for deterministic MMR reranking."""
        try:
            first = self._chunk_index[first_chunk_id]
            second = self._chunk_index[second_chunk_id]
        except KeyError as exc:
            raise RetrievalCorpusError(f"Unknown chunk ID: {exc.args[0]}") from exc
        return float(self._vectors[first] @ self._vectors[second])

    def hydrate(
        self,
        ranked_items: Iterable[dict[str, int | float | str]],
    ) -> list[Document]:
        """Hydrate cached ranked references from the verified local corpus."""
        documents: list[Document] = []
        for item in ranked_items:
            chunk_id = str(item["chunk_id"])
            try:
                chunk = self._chunks[self._chunk_index[chunk_id]]
            except KeyError as exc:
                raise RetrievalCorpusError(f"Unknown cached chunk ID: {chunk_id}") from exc
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
            }
            metadata.update(
                {
                    "embedding_model": self.model_name,
                    "similarity_score": float(item["similarity_score"]),
                    "rerank_score": float(item["rerank_score"]),
                    "dense_rank": int(item["dense_rank"]),
                    "final_rank": int(item["final_rank"]),
                    "validation_probability": float(
                        item["validation_probability"]
                    ),
                }
            )
            documents.append(
                Document(page_content=str(chunk["translation"]), metadata=metadata)
            )
        return documents

    def rerank_mmr(
        self,
        candidates: Sequence[Document],
        *,
        top_k: int,
        mmr_lambda: float,
        max_per_chapter: int,
    ) -> list[Document]:
        """Rerank dense candidates for relevance plus chapter-level diversity."""
        if not 0 <= mmr_lambda <= 1:
            raise ValueError("mmr_lambda must be between 0 and 1")
        if top_k < 1 or max_per_chapter < 1:
            raise ValueError("top_k and max_per_chapter must be positive")

        remaining = list(candidates)
        selected: list[Document] = []
        chapter_counts: dict[int, int] = {}
        while remaining and len(selected) < top_k:
            eligible = [
                document
                for document in remaining
                if chapter_counts.get(int(document.metadata["chapter"]), 0)
                < max_per_chapter
            ]
            if not eligible:
                break

            def score(document: Document) -> tuple[float, float, int]:
                relevance = float(document.metadata["similarity_score"])
                redundancy = max(
                    (
                        self.pairwise_similarity(
                            str(document.metadata["chunk_id"]),
                            str(chosen.metadata["chunk_id"]),
                        )
                        for chosen in selected
                    ),
                    default=0.0,
                )
                mmr_score = mmr_lambda * relevance - (1 - mmr_lambda) * redundancy
                return (
                    mmr_score,
                    relevance,
                    -int(document.metadata["dense_rank"]),
                )

            winner = max(eligible, key=score)
            rerank_score = score(winner)[0]
            final_rank = len(selected) + 1
            winner.metadata["rerank_score"] = rerank_score
            winner.metadata["final_rank"] = final_rank
            selected.append(winner)
            chapter = int(winner.metadata["chapter"])
            chapter_counts[chapter] = chapter_counts.get(chapter, 0) + 1
            remaining.remove(winner)
        return selected


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
