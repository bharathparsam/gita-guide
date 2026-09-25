from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.retrieval.nvidia_embeddings import (
    NEMOTRON_EMBEDDING_DIMENSIONS,
    NvidiaEmbeddingError,
    NvidiaNemotronEmbeddings,
)


def embedding_response(count: int, *, dimensions: int = NEMOTRON_EMBEDDING_DIMENSIONS) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "model": "nvidia/nemotron-3-embed-1b",
        "data": [
            {"object": "embedding", "index": index, "embedding": [0.1] * dimensions}
            for index in range(count)
        ],
    }
    return response


def test_nvidia_embeddings_use_passage_and_query_input_types() -> None:
    session = Mock()
    session.post.side_effect = [embedding_response(2), embedding_response(1)]
    embeddings = NvidiaNemotronEmbeddings(
        api_key="test-key",
        batch_size=2,
        session=session,
    )

    documents = embeddings.embed_documents(["Verse one", "Verse two"])
    query = embeddings.embed_query("fear of failure")

    assert len(documents) == 2
    assert len(query) == NEMOTRON_EMBEDDING_DIMENSIONS
    passage_payload = session.post.call_args_list[0].kwargs["json"]
    query_payload = session.post.call_args_list[1].kwargs["json"]
    assert passage_payload["input_type"] == "passage"
    assert passage_payload["input"] == ["Verse one", "Verse two"]
    assert query_payload["input_type"] == "query"
    assert query_payload["input"] == ["fear of failure"]
    assert "dimensions" not in passage_payload


def test_nvidia_embeddings_batch_document_requests() -> None:
    session = Mock()
    session.post.side_effect = [embedding_response(2), embedding_response(1)]
    embeddings = NvidiaNemotronEmbeddings(
        api_key="test-key",
        batch_size=2,
        session=session,
    )

    vectors = embeddings.embed_documents(["one", "two", "three"])

    assert len(vectors) == 3
    assert session.post.call_count == 2


def test_nvidia_embeddings_reject_wrong_dimensions() -> None:
    session = Mock()
    session.post.return_value = embedding_response(1, dimensions=4)
    embeddings = NvidiaNemotronEmbeddings(api_key="test-key", session=session)

    with pytest.raises(NvidiaEmbeddingError, match="dimension"):
        embeddings.embed_query("test")
