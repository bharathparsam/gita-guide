# Grounded guidance generation

## Entry contract

The generator accepts only `GroundedGenerationInput`. This contract requires one
to five passages that survived deterministic source checks, local retrieval,
MMR reranking, and both JEV relevance/groundability decisions. The builder fails
closed when `ready_for_generation` is false or no approved passages remain.

## Model and prompt

Generation uses LangChain `ChatNVIDIA` against NVIDIA's OpenAI-compatible NIM
endpoint. The default model is `nvidia/nemotron-3.5-lightning-30b-a3b`; it can be
replaced behind the same adapter through environment configuration.

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
- asks for acknowledgement, a plain-language principle, and practical next steps;
- provides an explicit abstention response for insufficient evidence.

## Post-generation gates

The response is not returned immediately:

1. Empty, non-text, truncated, or reasoning-leaking responses fail closed.
2. At least one exact Bhagavad Gita citation is required.
3. Every citation must map to a JEV-approved input passage; unsupported citations
   fail the request.
4. NVIDIA content safety runs again as an output rail. A blocked or escalated
   decision is never returned to the caller.
5. The final response records its model, provider request ID when exposed by the
   adapter, LangChain run ID, citations, grounded chunk IDs, prompt version,
   response fingerprint, metrics, and audit event.

Raw prompts and generated guidance are excluded from application logs by default.
LangSmith may contain runnable inputs and outputs when tracing is enabled, so its
production retention and access policy remains a deployment gate.

## Remaining quality gate

Citation validity proves that cited passages were supplied; it does not prove
that every generated claim is entailed by them. Before exposing generation through
the public API, add a labeled grounded-response evaluation set and enforce
faithfulness, citation precision, helpfulness, safety, and abstention thresholds.
