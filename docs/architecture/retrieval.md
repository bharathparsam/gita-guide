# Retrieval architecture

## Source and chunk contract

The canonical source is the public-domain Swami Swarupananda translation recorded
in `data/sources.json`. Ingestion verifies its SHA-256 checksum before extraction.

Chunk boundaries follow the printed verse structure:

- One chunk per independently translated verse.
- A printed combined range, such as 1.4-6, remains one chunk.
- No arbitrary fixed-token overlap is introduced.
- Every chunk preserves source, chapter, full chapter title, verse range, speaker,
  PDF page, translation, and enriched retrieval text.

This strategy gives stable citations and prevents a token splitter from joining
unrelated verses or breaking an indivisible translated range. The current corpus
contains 671 chunks covering all 700 verses exactly once. Chunks have a median of
42 words, a 95th percentile of 55 words, and a maximum of 124 words.

If evaluation shows that short verses lack context, retrieval should expand the
winning verse with adjacent verses after ranking. It should not mutate the canonical
chunk boundary or citation.

## Embeddings

`NvidiaNemotronEmbeddings` implements LangChain's `Embeddings` interface and calls
`nvidia/nemotron-3-embed-1b` through `/v1/embeddings`.

- Documents use `input_type=passage`.
- User retrieval queries use `input_type=query`.
- The model returns 2048-dimensional float vectors.
- Application logs contain prompt fingerprints and sizes, not raw text.
- Requests use bounded retry and a circuit breaker.

The hosted NVIDIA development endpoint is not treated as a production SLA. An
approved hosted contract or self-hosted NIM can replace it behind the same adapter.

## Bundled vector storage

The 671 normalized float32 vectors are stored as a 5.2 MB NumPy matrix in
`data/processed/gita_embeddings.npy`. Its sidecar metadata records the embedding
model, dimensions, row count, normalization contract, query/passage modes, chunk
checksum, and embedding-file checksum.

The matrix ships as an immutable application artifact and is opened with NumPy
memory mapping. The operating system can share its file-backed pages between
workers on the same host. A query performs one matrix-vector multiplication and a
stable descending sort; no vector database or retrieval network call is required.

Runtime refuses to load the artifact if its chunk checksum, vector checksum, row
count, dimensions, or normalization contract is inconsistent. Corpus or model
changes must generate a new matrix and sidecar together during the build process;
embeddings are never regenerated during application startup.

## Quality gate before public use

The classification API must not call retrieval until a labeled retrieval dataset
sets and passes thresholds for:

1. Recall@5 for all acceptable gold verses.
2. Mean reciprocal rank for the first relevant verse.
3. Chapter and verse citation completeness.
4. Abstention behavior below a tuned relevance threshold.
5. Stability across embedding-model and corpus revisions.

The relevance threshold must be learned from labeled examples; it must not be copied
from another embedding model because score distributions are model-specific.
