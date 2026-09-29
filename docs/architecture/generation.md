# Grounded guidance generation

## Entry contract

The generator accepts only `GroundedGenerationInput`. This contract requires one
to five passages that survived deterministic source checks, local retrieval,
MMR reranking, and both JEV relevance/groundability decisions. The builder fails
closed when `ready_for_generation` is false or no approved passages remain.

## Model and prompt

Generation uses LangChain's OpenAI-compatible `ChatOpenAI` adapter against
OpenRouter. The default model is `google/gemma-4-31b-it`; it can be replaced through
environment configuration. OpenRouter can route the model across eligible upstream
providers. The optional `google/gemma-4-31b-it:free` route remains capacity-limited
and has no uptime SLA, so it is not the reliability-oriented default.

Extended thinking is disabled for this user-facing request. In addition to
keeping the response concise, this prevents reasoning traces from consuming the
completion budget or becoming user-visible. A response that is truncated or
contains known reasoning-trace markers fails closed.

The versioned prompt:

- treats the user message, classification, and passages as untrusted data;
- permits scriptural claims only from supplied passages;
- requires exact supplied `[Bhagavad Gita chapter.verse]` citations;
- prohibits invented verses, diagnoses, promises, shame, and claims of divine
  authority;
- prefers concise descriptive paraphrases and avoids reproducing imperative,
  condemnatory, or divine-first-person translation wording as user-facing advice;
- requires a stable two-section response: `What Krishna said` and
  `How to overcome`, with the trait label supplied deterministically from the
  classification rather than invented by the model;
- emits a typed presentation contract containing the label, both generated
  sections, exact verse reference, and source-extracted Sanskrit sloka so the live
  UI uses the same card structure as offline mode;
- requires practical steps to be ordinary, low-risk actions in the user's stated
  situation rather than abstract restatements;
- excludes unrequested breath restriction, fixed-gaze exercises, and other
  specialized contemplative techniques from general emotional guidance;
- provides an explicit abstention response for insufficient evidence.

## Post-generation gates

The response is not returned immediately:

1. Empty, non-text, truncated, reasoning-leaking, or structurally malformed
   responses fail closed.
2. Both required reflection sections must be present and non-empty, and at least
   one exact Bhagavad Gita citation is required.
3. Every citation must map to a JEV-approved input passage; unsupported citations
   fail the request.
4. NVIDIA content safety runs again as an output rail. A blocked or escalated
   decision is never returned to the caller.
5. A separate OpenRouter/JEV decision scores faithfulness, citation coverage,
   helpfulness, and user agency against explicit runtime thresholds. Its agency
   rubric distinguishes clearly attributed source evidence from the assistant's
   framing, while still rejecting source wording used to pressure or shame a user.
   Its helpfulness rubric permits modest everyday applications of an evidenced
   principle, while rejecting generic restatement or an unrequested specialized
   practice that does not answer the user's real situation.
   The NVIDIA and JEV post-generation checks execute concurrently after deterministic
   validation because neither depends on the other's result. Safety, faithfulness,
   citation coverage, and agency are hard gates and continue to fail closed.
   Helpfulness is a quality gate: a helpfulness-only miss receives one targeted
   rewrite, then returns a typed curated-fallback signal rather than an HTTP 502.
6. Generation has a separate bounded draft budget (three attempts by default):
   the initial response, at most one deterministic repair, and at most one
   dimension-targeted semantic repair. Helpfulness-only failures stop after one
   repair so a subjective boundary score cannot consume a third model call. This is intentionally independent from
   transport retry settings. Each draft gets its own bounded transport-retry budget
   with exponential backoff and jitter, so a transient provider failure does not
   consume a semantic-repair attempt. Exhausting the draft budget abstains rather than returning
   a weak answer.
7. Exhausted transient provider failures return HTTP `503` with `Retry-After` and a
   provider-availability message; they are not mislabeled as content-safety failures.
8. The final response records its model, provider request ID when exposed by the
   adapter, LangChain run ID, citations, grounded chunk IDs, prompt version,
   response fingerprint, metrics, and audit event. The audit record includes draft,
   repair, and provider-attempt counts plus model, output-safety, answer-validation,
   parallel-check wall-clock, and total durations. LangSmith uses one parent pipeline
   span, attempt metadata on each model call, and separate child spans for both
   concurrent post-generation checks.

Raw prompts and generated guidance are excluded from application logs by default.
LangSmith may contain runnable inputs and outputs when tracing is enabled, so its
production retention and access policy remains a deployment gate.

Hard quality rejections remain generic in production. Development responses include
the failed dimensions and scores. A helpfulness-only response uses the distinct
`guidance_not_helpful` code with its curated fallback trait; the Next.js boundary
returns the matching offline card with HTTP 200 and does not save that fallback as
conversation memory. All environments return an `X-Request-ID` for correlation.

## Release status

The labeled answer and adversarial datasets, live runners, and combined release
manifest are implemented. The current manifest fails, so `/v1/guidance` remains
hidden by default. Passing automation is necessary but still requires named domain,
security, and privacy review plus target-environment load/soak evidence.
