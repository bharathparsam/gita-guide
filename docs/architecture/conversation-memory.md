# Conversation memory

Conversation memory is a bounded, stateless API contract. The API does not own
users or persist chat history. The guest-only web client keeps context in React
memory for the lifetime of the current page. Refreshing or closing the page
discards messages, summary, and recent turns.

## Safety boundary

The current message is the only value sent through input safety and JEV intent
classification. A normalized rolling summary and recent completed exchanges may
be used for retrieval continuity and answer generation. They are always labeled
as untrusted data and cannot replace the current-message classification.

The public context is capped at a 2,000-character summary and eight recent turns.
Each turn is capped at 2,000 characters. Turns must be complete alternating
`user`/`assistant` exchanges. Invisible control and bidirectional formatting
characters are removed before prompt construction.

The Next.js proxy accepts only the bounded guest context contract and rate-limits
the request before any provider call.

## Guidance contract

`POST /v1/guidance` accepts optional memory:

```json
{
  "message": "What can I do while I wait?",
  "conversation": {
    "schema_version": "1.0",
    "summary": "The user is waiting for an interview result.",
    "recent_turns": [
      {"role": "user", "content": "I completed my interview."},
      {"role": "assistant", "content": "Waiting can feel uncertain."}
    ]
  }
}
```

The response includes the validated guidance plus the next `conversation` value,
`summary_updated`, `summary_deferred`, and `summarized_turn_count`. The web client
keeps the returned context only for the current page session.

By default, summarization starts at six recent turns and retains the latest two.
The same configured OpenRouter generation model is used with temperature zero. If an
automatic summary fails after guidance has passed its safety and grounding gates,
guidance still returns with bounded recent memory and `summary_deferred: true`.

## Independent summary contract

`POST /v1/conversations/summarize` is authenticated by the same `X-API-Key`
policy as the other API routes. It accepts `{ "conversation": ... }`. Below the
configured threshold it returns the input unchanged and does not call NVIDIA.
At or above the threshold it returns a rolled summary and the retained turns.

This endpoint supports an application layer that persists full message history
separately, retries deferred summarization, or runs summarization asynchronously.
