from __future__ import annotations

from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.retrieval.gita_vector_retriever import GitaVectorRetriever
from app.retrieval.nvidia_embeddings import NvidiaNemotronEmbeddings


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHUNKS_PATH = _PROJECT_ROOT / "data/processed/gita_chunks.jsonl"
DEFAULT_EMBEDDINGS_PATH = _PROJECT_ROOT / "data/processed/gita_embeddings.npy"
DEFAULT_METADATA_PATH = _PROJECT_ROOT / "data/processed/gita_embeddings.metadata.json"


def build_local_gita_retriever(
    *,
    embeddings: Embeddings | None = None,
    chunks_path: Path = DEFAULT_CHUNKS_PATH,
    embeddings_path: Path = DEFAULT_EMBEDDINGS_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> GitaVectorRetriever:
    """Build the checksum-verified, memory-mapped bundled retriever."""
    resolved_embeddings = embeddings or NvidiaNemotronEmbeddings.from_environment()
    return GitaVectorRetriever.from_files(
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        metadata_path=metadata_path,
        embeddings=resolved_embeddings,
    )
