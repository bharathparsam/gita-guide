# Retrieval architecture

## Source and chunk contract

The canonical source is the user-provided *Bhagavad-gita As It Is* edition recorded
in `data/sources.json`. Ingestion verifies its SHA-256 checksum before extraction.
The manifest deliberately does not claim redistribution rights for the source.

The parser identifies all 18 chapters, 653 printed `TEXT`/`TEXTS` sections, and
their translation and purport sections. It accounts for printed combined verse
ranges and validates exact coverage of all 700 verses. Long content is split
recursively using these separator priorities:

- Paragraph breaks (`\n\n`).
- Line breaks (`\n`).
- Sentence-ending periods.
- Spaces, followed by a character-level fallback only when necessary.

The defaults are 1,200 characters and up to 160 characters of overlap. The current
corpus contains 1,860 chunks: 653 translation chunks and 1,207 purport chunks.
Every chunk preserves source, chapter title, verse range, canonical verse speaker,
section type, content author, source PDF page, and enriched retrieval text.
Translation and commentary remain separately attributable throughout retrieval and
generation; purport text must never be presented as Krishna's direct wording.

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

The 1,860 normalized float32 vectors are stored as a 15 MB NumPy matrix in
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

## Filter, rerank, and cache pipeline

Retrieval is deliberately wider than the final grounding context:

1. The pre-filter rejects out-of-scope and low-confidence classifications.
2. Corpus metadata is restricted to the provenance-approved source, verse
   translations whose canonical speaker is Krishna, and their source-extracted
   Sanskrit slokas. Purports remain indexed for future controlled experiments but
   cannot enter the live `What Krishna said` generation path.
3. Dense cosine search retrieves 20 candidates by default.
4. The post-filter removes candidates below `RETRIEVAL_MINIMUM_SCORE` and never
   pads an irrelevant result merely to reach the configured passage limit.
5. The curated trait-to-verse catalog contributes one anchor candidate. An anchor
   is guaranteed consideration but never bypasses JEV relevance validation.
6. Deterministic maximal marginal relevance reranking balances semantic relevance
   with vector diversity. A chapter cap prevents near-duplicate passages from one
   chapter from occupying the complete context.
7. One batched JEV Decisions request independently scores five reranked passages
   against the original message and Phase 1 classification.
8. Passages below `RETRIEVAL_VALIDATION_THRESHOLD` are removed. Approved passages
   are ordered by JEV relevance and MMR score, and final ranks are compacted.
9. At most three JEV-approved, citation-ready passages are passed to generation.

The defaults are `candidate_k=20`, `validation_k=5`, `top_k=3`, `mmr_lambda=0.8`,
and at most two passages per chapter. These values and the anchor-aware pipeline
version are cache inputs. The minimum score
is currently a conservative zero floor and must be tuned from the labeled
retrieval evaluation set before the public grounded-answer endpoint is enabled.
The initial JEV validation threshold is `0.65`; this threshold and the validator
prompt and model versions are also part of the cache identity.

JEV is a semantic relevance judge, not the source-integrity mechanism. PDF and
chunk checksums, speaker/source allowlists, and citation metadata remain
deterministic controls. The validator treats user text and passages as data and
is instructed not to follow embedded instructions. An invalid or unavailable JEV
response fails closed: no unvalidated context can reach generation. If all
passages are rejected, `ready_for_generation=false` and the future response layer
must abstain rather than generate unsupported guidance.

`build_grounded_generation_input` is the explicit handoff boundary to the future
LLM adapter. Its typed contract requires one to five passages and rechecks that
every passage's JEV probability meets the recorded validation threshold. It raises
`GenerationNotReadyError` when the retrieval result is not ready, so provider code
cannot accidentally generate without approved evidence.

Successfully validated retrievals are cached for six hours by default. Redis receives an
opaque HMAC key derived from the normalized retrieval query and all
decision-changing corpus, model, filter, and reranker versions. The value stores
only chunk IDs, dense/MMR/JEV scores, ranks, validation model/request metadata,
candidate count, and a timestamp. Verse text and
vectors are not copied into Redis; cache hits rehydrate their chunk IDs from the
checksum-verified local corpus. Empty and failed retrievals are not cached. Cache
read, corruption, or write failures are logged and fail open to local retrieval;
Redis availability does not become a retrieval availability dependency.

The CLI composes Phase 1 and retrieval beneath one LangSmith parent run. The
retrieval stage includes pre-filter, retrieve/rerank, JEV-validation, and cache
events, while each JEV prompt and response carries the same request ID.
Structured logs cover retrieval start, cache hit/miss, candidate count,
anchor and selected candidate IDs, every JEV relevance decision, post-filter
drops, cache writes, final chunk IDs and citations, and duration. Raw retrieval
queries are fingerprinted rather than logged by default,
and the server request ID is injected into provider logs through request context.

## Quality gate before public grounded answers

The classification API must not call retrieval until a labeled retrieval dataset
sets and passes thresholds for:

1. Recall@5 for all acceptable gold verses.
2. Mean reciprocal rank for the first relevant verse.
3. Chapter and verse citation completeness.
4. Abstention behavior below a tuned relevance threshold.
5. Stability across embedding-model and corpus revisions.

The relevance threshold must be learned from labeled examples; it must not be copied
from another embedding model because score distributions are model-specific.
