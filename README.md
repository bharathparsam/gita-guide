# Gita Guide

Gita Guide is an early-stage Python application for giving source-grounded,
reflective guidance inspired by the Bhagavad Gita. It first applies input safety
checks, classifies the user's situation and emotional state, and will retrieve
relevant verses before generating guidance.

The current version accepts messages through a CLI or authenticated HTTP API and uses
[JEV](https://openrouter.ai/typesafe/jev-1.13) through OpenRouter's Decisions API
to identify:

- Whether the message is in scope for reflective life guidance
- The primary life situation
- The primary emotion
- The underlying inner conflict

The classification, evaluation, safety boundary, cache, audit, metrics, and
source-corpus foundations are implemented. The vector-retrieval component is
implemented separately; retrieval-quality evaluation and final grounded guidance
remain the next product layer.

Phase 1 is implemented as a LangChain pipeline with correlated JSON logs and
optional LangSmith tracing.

## Requirements

- Python 3.10 or newer
- An [OpenRouter](https://openrouter.ai/) API key with access to JEV
- Optional: an NVIDIA API key for its hosted Nemotron content-safety endpoint
- Optional: a LangSmith API key for hosted LangChain traces

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Copy the example environment file and add your key:

```bash
cp .env.example .env
```

The `.env` file is ignored by Git and should not be committed.

## Run the application

From the project root, run:

```bash
python -m app.main
```

Enter a personal situation when prompted:

```text
Tell me what you're going through: I worked hard but failed my interview and now I feel useless.
```

The application returns a structured classification similar to:

```json
{
  "schema_version": "1.0",
  "in_scope": true,
  "in_scope_probability": 0.99,
  "primary_situation": "fear_of_failure",
  "primary_situation_confidence": 0.92,
  "primary_emotion": "sadness",
  "primary_emotion_confidence": 0.96,
  "root_conflict": "attachment_to_results",
  "root_conflict_confidence": 0.91,
  "needs_review": false,
  "low_confidence_fields": [],
  "provider_request_id": "decision-id",
  "model": "typesafe/jev-1.13-snapshot"
}
```

JEV is probabilistic, so classifications can vary between requests.

### HTTP API

Start the API with:

```bash
uvicorn app.api.application:app --host 127.0.0.1 --port 8000
```

Classify a message:

```bash
curl -X POST http://127.0.0.1:8000/v1/classifications \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-app-api-key' \
  -H 'Idempotency-Key: mobile-request-123' \
  -d '{"message":"I am worried that my effort will not lead to success."}'
```

The server generates the authoritative UUID request ID, returns it in both the
response body and `X-Request-ID`, and preserves a separately validated optional
`X-Client-Request-ID`. Public liveness and readiness endpoints are available at
`/health/live` and `/health/ready`. The Prometheus endpoint `/metrics` uses the
same API-key authentication policy as classification.

## How it works

```text
User message
    |
    v
LangChain Phase 1 pipeline (one correlated trace)
    |
    +--> Input normalization and validation
    |
    +--> Local explicit-language and crisis rail
    |
    +--> Optional NVIDIA Nemotron content-safety rail
    |
    +--> Exact HMAC-keyed cache / idempotency lookup
    |       |
    |       +--> cache miss -> JEV classifier -> OpenRouter Decisions API
    |
    v
ClassificationResult
    |
    v
Verse retrieval and grounded guidance (next phase)
```

JEV receives the message and four typed questions in one request. It uses a
`noul` question for the in-scope decision and `choice` questions for situation,
emotion, and root conflict. Returned choices are validated against the local
taxonomy before a `ClassificationResult` is created.

Safety runs before every cache lookup and before JEV, so cached results cannot
bypass the current safety policy. Self-harm indicators use a separate escalation
route and are not treated as profanity.

The pipeline is composed from LangChain `RunnableLambda` stages. The safety and
classification implementations remain ordinary Python services, so they can be
unit tested without calling LangSmith or an external provider.

## Logging and LangSmith traces

The CLI writes one-line JSON application logs to stderr. A generated `request_id`
connects validation, safety, JEV, and the final result. Each received user prompt
and each outbound model prompt emits a log event containing an HMAC-SHA256 fingerprint
and character count. Safety decisions, model identifiers, provider request IDs,
classification labels, review decisions, and stage durations are also logged.

Raw prompt content is deliberately excluded from application logs by default
because messages may contain private emotional or health information. To include
the complete text in development logs, set:

```dotenv
LOG_PROMPT_CONTENT=true
```

Do not enable that setting in production without a documented consent,
retention, access-control, and deletion policy. API keys and authorization headers
are never part of the logged prompt payload.

To send the LangChain execution tree to LangSmith, configure:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=gita-guide-phase-1
```

The LangSmith trace contains the parent Phase 1 run and separate input-validation,
guardrail, and JEV-classification spans. LangChain passes step inputs and outputs
to the tracer, so keep tracing disabled for sensitive production traffic until an
approved data-handling policy is in place. Application logging continues to work
when LangSmith is disabled or unavailable.

LangSmith is the model-development trace, not the authoritative audit store. The
service also writes versioned, append-only, prompt-free audit records to
`AUDIT_LOG_PATH`. Prometheus metrics cover request outcomes and latency, guardrail
decisions, classification review rates, provider health, and cache behavior.

## Caching and idempotency

Development defaults to a process-local TTL cache. A single local API process
does not need Upstash. Multi-instance and serverless deployments should use the
shared Upstash REST backend so cache entries and idempotency claims survive process
boundaries:

```dotenv
APP_ENVIRONMENT=production
CACHE_BACKEND=upstash
UPSTASH_REDIS_REST_URL=https://replace-with-your-database.upstash.io
UPSTASH_REDIS_REST_TOKEN=replace-with-your-token
CACHE_HMAC_SECRET=a-random-secret-containing-at-least-32-bytes
CLASSIFICATION_CACHE_TTL_SECONDS=3600
IDEMPOTENCY_TTL_SECONDS=86400
```

Cache keys are opaque HMACs over the normalized message and every decision-changing
version: tenant, model, taxonomy, prompt, thresholds, and result schema. Raw text
is never used as a Redis key. Cache values are encoded before transport, but are
not application-encrypted; configure Upstash access and retention accordingly.
Low-confidence and `needs_review` classifications are not cached. Concurrent
identical cache misses are coalesced within a worker,
and shared Redis idempotency claims use atomic ownership checks. Provider errors are
never cached.

Production mode fails startup when API authentication, shared Redis caching, the
NVIDIA fail-closed policy, durable audit output, or HMAC fingerprint secrets are
missing. This prevents development defaults from being deployed accidentally.

## Project structure

```text
app/
├── api/                         # FastAPI ingress, middleware, and lifecycle
├── cache/                       # Redis/memory cache and idempotency primitives
├── classifiers/
│   ├── jev_classifier.py       # OpenRouter request and response validation
│   └── taxonomy.py             # Supported classification labels
├── guardrails/
│   └── input_safety.py         # Local and NVIDIA input-safety rails
├── models/
│   └── classification.py       # Structured result model
├── observability/
│   ├── audit.py                # Append-only audit sink contract
│   ├── logging.py              # Correlated structured JSON logs
│   ├── metrics.py              # Low-cardinality metric contract
│   └── prometheus.py           # Prometheus adapter
├── reliability/                # Retry and circuit-breaker primitives
├── retrieval/                  # Verified vector retrieval LangChain stage
├── services/
│   └── classification_service.py # LangChain Phase 1 pipeline
├── config.py                   # Environment configuration
└── main.py                     # CLI entry point
evals/
├── classification_cases.json  # Versioned labeled evaluation set
├── reports/                    # Measured JEV evaluation reports
└── run_classification_evals.py
data/
├── raw/                        # Provenance-tracked source PDF
├── processed/                  # Verse-aware JSONL chunks
└── sources.json                # Source license, URL, and checksum
scripts/
├── ingest_gita_pdf.py          # Validated PDF-to-chunk pipeline
└── embed_gita_chunks.py        # Optional multilingual embedding build
tests/
├── test_classifier.py          # Mocked classifier and safety tests
├── test_evaluation_dataset.py  # Evaluation-data contract checks
├── test_gita_corpus.py         # Corpus provenance and coverage checks
└── test_jev.py                 # Manual live JEV integration script
```

## Classification taxonomy

The supported labels are defined in `app/classifiers/taxonomy.py`.

Situation examples include fear of failure, outcome anxiety, comparison, anger,
grief, confusion, lack of motivation, purpose, discipline, and relationship
conflict.

Emotion examples include fear, sadness, anger, envy, guilt, confusion,
frustration, hopelessness, and calm.

Root-conflict examples include attachment to results, fear, comparison, ego,
desire, duty conflict, lack of self-control, loss, and uncertainty.

Each dimension also includes an `other` category.

The API result includes confidence for every categorical decision, the in-scope
probability, the resolved model snapshot, and the provider request ID so decisions
can be audited.

Any decision below `CLASSIFICATION_MIN_CONFIDENCE` is marked `needs_review`
instead of being treated as equally reliable. Evaluation reports include review
rate and selective joint accuracy for the classifications that would be accepted
automatically.

## Input safety and NVIDIA guardrails

The default pipeline always applies a deterministic local first-pass rail. It:

- Blocks configured explicit or obfuscated language before classification
- Escalates clear self-harm language to a dedicated safety message
- Allows ordinary grief, anger, and non-graphic requests for emotional support

For development, add `NVIDIA_API_KEY` to `.env`. The application then uses
NVIDIA's hosted OpenAI-compatible endpoint with the current
[`nvidia/nemotron-3.5-content-safety`](https://build.nvidia.com/nvidia/nemotron-3.5-content-safety)
model. No key value is logged or included in application output.

NVIDIA labels this a free development endpoint, but it is a rate-limited trial
service rather than a production SLA. NVIDIA also states that hosted trial inputs
and outputs may be recorded, so do not send confidential or personally identifying
user data through it without an appropriate privacy and consent design.

Test the configured endpoint with a synthetic message:

```bash
python -m scripts.check_nvidia_guardrail "I am disappointed about failing an exam."
```

For production, either use an approved hosted deployment or self-host the model
behind the same OpenAI-compatible interface. Set:

```dotenv
NVIDIA_GUARDRAIL_REQUIRED=true
```

That setting makes the application fail closed if the model-based safety rail is
unavailable. A self-hosted model avoids per-request vendor charges, but compute
and operations are not cost-free. NVIDIA documents input, retrieval, dialog,
execution, and output rail stages in its
[guardrail types guide](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/rail-types).

The local lexical layer is defense in depth; it is not represented as a substitute
for the NVIDIA safety model.

## Classification evaluations

`evals/classification_cases.json` currently contains 26 labeled cases covering
every situation category, ambiguous acceptable labels, and out-of-scope inputs.
Run the live evaluation with:

```bash
python -m evals.run_classification_evals \
  --repeats 3 \
  --min-joint-accuracy 0.85 \
  --output evals/reports/latest.json
```

Each repeat makes one billable JEV request per case. Reports include per-field
accuracy, joint accuracy, and every mismatch. Because JEV is probabilistic, use
multiple repeats before accepting a taxonomy or prompt change.

The first single-pass baseline achieved 80.77% joint accuracy. After clarifying
taxonomy boundaries, a three-repeat run (78 requests) achieved 93.59% joint
accuracy with no provider errors. A subsequent single pass varied to 88.46%, but
the 60% confidence review threshold routed every error for review: the 18
auto-accepted cases had 100% selective joint accuracy, with a 30.77% review rate.
These are small development-set results, not production accuracy claims.

Run the deterministic test suite separately:

```bash
python -m pytest -q
```

## Bhagavad Gita corpus

The repository includes a public-domain, verse-numbered English translation by
Swami Swarupananda, first published in 1909. Its provenance URL, retrieval date,
license status, and SHA-256 checksum are recorded in `data/sources.json`.

Rebuild the retrieval chunks with:

```bash
python -m pip install -r requirements-rag.txt
python scripts/ingest_gita_pdf.py
```

The ingestion pipeline verifies the source checksum and validates exact coverage
of all 700 verses across 18 chapters. It produces 671 JSONL chunks because the
source combines a few adjacent verses into single translated passages. Every chunk
contains a stable ID, chapter, verse range, speaker, source PDF page, translation,
and retrieval text.

The chunker follows the scripture's semantic structure rather than arbitrary token
windows. Each printed verse is one retrievable unit; when the source translator
combines adjacent verses, that range remains one indivisible chunk. There is no
synthetic overlap. This produces 671 chunks for 700 verses, with a median of 42
words and a maximum of 124 words. Chapter, title, verse range, speaker, source PDF
page, translation, source ID, and retrieval text are retained for citations.

Regenerate the bundled vector artifact with:

```bash
python -m scripts.embed_gita_chunks
```

The build uses NVIDIA `nvidia/nemotron-3-embed-1b` through the OpenAI-compatible
embedding endpoint with `input_type=passage`. Its normalized 2048-dimensional
float vectors are saved in `data/processed/gita_embeddings.npy`. The 5.2 MB matrix
ships with the application and is memory-mapped at startup, so similarity search
does not require a vector database or network call.

The hosted NVIDIA endpoint is appropriate for development, not an enterprise SLA.
Indexing sends only the public-domain Gita text. Runtime retrieval sends the user's
retrieval query to the embedding endpoint, so production requires the same privacy
and vendor review as the safety model.

`GitaVectorRetriever` loads the bundled artifact only after verifying the chunk
and embedding checksums, row count, dimensions, and normalization flag. It returns LangChain
`Document` objects containing chapter, verse, PDF page, speaker, source ID, and
similarity score for later citations. At runtime, NVIDIA creates only the query
embedding with `input_type=query`; cosine ranking then runs locally over all 671
vectors. The retrieval stage combines the original message with Phase 1 situation,
emotion, and root-conflict labels. It is not yet connected to the public
classification endpoint because retrieval
relevance thresholds must first be evaluated against a labeled dataset.

Run a direct retrieval smoke test with:

```bash
python -m scripts.search_gita \
  "I am anxious that my work will not produce the result I want" \
  --top-k 5
```

## Live JEV check

To call JEV directly with the sample payload in the integration script, run:

```bash
python tests/test_jev.py
```

This script makes a real, billable OpenRouter API request. It is currently a
manual integration check rather than an isolated automated test.

## Current status

Implemented:

- Interactive CLI input
- LangChain Phase 1 orchestration for validation, safety, and classification
- Correlated JSON prompt, safety, classification, failure, and timing logs
- Optional LangSmith traces with named spans for every Phase 1 stage
- FastAPI ingress with auth, body limits, trusted request IDs, safe errors, and health checks
- Redis/in-memory exact classification cache, atomic idempotency, and single-flight control
- Bounded retries and provider circuit breakers
- HMAC prompt fingerprints and append-only durable audit records
- Prometheus metrics endpoint
- OpenRouter/JEV classification with confidence and provider metadata
- Strict response-shape and taxonomy validation
- Local input safety, crisis escalation, and optional NVIDIA model-based safety
- Versioned classification dataset and live evaluation runner
- Public-domain source PDF with provenance and checksum
- Verse-aware chunks covering all 700 verses
- NVIDIA Nemotron embedding client with query/passage separation
- Bundled, memory-mapped 671-row embedding matrix with checksum metadata
- Provenance-checked LangChain local vector retriever with citation metadata
- Unit, concurrency, failure, API, cache, audit, metrics, and corpus tests

Next:

- Retrieval relevance dataset and quality gates
- A mapping layer from classification dimensions to Gita themes
- Grounded response generation that quotes only retrieved verses
- NVIDIA output and retrieval rails in addition to the input rail
- Distributed load/soak testing, deployment alerts, rate limits, and production deployment

The architecture and production-readiness gates are documented in
`docs/architecture/phase-1.md`. Passing the local suite does not by itself declare
the system production-ready; Redis, provider, alerting, security, privacy, and
load gates must also pass in the target environment.
