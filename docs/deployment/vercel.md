# Private-beta deployment on Vercel

Vercel is the recommended first host for this repository. It can deploy the
FastAPI backend and the frontend as two projects from the same repository. The
Python runtime is currently Beta, so this is suitable for the expected private
beta of 5–10 users, but it is not yet the final production-runtime decision.

## Deployment layout

Create two Vercel projects from the same Git repository:

| Project | Root directory | Purpose |
| --- | --- | --- |
| `gita-guide-api` | repository root | FastAPI, model calls, retrieval and secrets |
| `gita-guide-web` | `web/` | Browser UI and server-side API proxy |

The backend entrypoint is `index.py`. It exports the existing FastAPI app, so
the API keeps its current paths such as `/health/live` and `/v1/guidance`.
The versioned configuration includes the local processed Gita chunks,
embeddings and metadata in the backend function bundle. The approximately 6 MB
corpus is read-only and safe to bundle; it does not require a vector database
at this scale.

The web app is guest-only. Conversation context exists only in the browser
page's memory and is not persisted. The Python service remains stateless: it
receives bounded context and returns the next rolling-memory state.

## 1. Create the backend project

1. Import the Git repository in Vercel.
2. Set the project root to the repository root.
3. Select the FastAPI framework preset if it is not detected automatically.
4. Enable Deployment Protection for the private beta.
5. Add the variables from `.env.vercel.example` in Project Settings. Use real,
   independently generated values and apply them to Preview and Production as
   appropriate.
6. Deploy a Preview first.

The same flow is available through the CLI:

```bash
vercel link
vercel env add APP_API_KEY
vercel deploy
```

Do not use `vercel env pull` into a tracked file. Do not expose `APP_API_KEY` to
browser JavaScript. The frontend should call its own server-side proxy, which
adds the API key when calling the backend.

## 2. Keep the release gate truthful

The checked-in guidance release report is not approved. Therefore the template
keeps both flags false:

```text
GUIDANCE_API_ENABLED=false
GUIDANCE_RELEASE_APPROVED=false
GUIDANCE_PRIVATE_BETA_ENABLED=false
```

Do not set `GUIDANCE_RELEASE_APPROVED=true` merely to make a deployment work.
For the limited beta, record the known quality/provider limitations and set
`GUIDANCE_API_ENABLED=true` plus `GUIDANCE_PRIVATE_BETA_ENABLED=true`. Keep
`GUIDANCE_RELEASE_APPROVED=false`. The backend path still requires its API key;
only the Next.js server proxy holds it. Guest access makes the frontend public,
so configure and verify the Upstash guest rate limit before enabling it. Remove
the beta exception or pass the complete release gates before a general release.

## 3. Understand the filesystem boundary

The packaged Gita corpus is read-only, which is compatible with Vercel. Runtime
files are not durable. `/tmp` may disappear between invocations and instances.

The current production configuration requires `AUDIT_LOG_PATH`, so the example
uses `/tmp/gita-guide/phase1.jsonl` to let the application start. This is only a
temporary compatibility setting, not an enterprise audit log. Vercel logs and
LangSmith traces help diagnose requests, but neither is a substitute for the
application's append-only durable audit sink.

Before a general release, replace the JSONL sink with durable centralized
storage and define retention, access and deletion policy. Do not silently copy
raw user messages into an audit store; retain request IDs, decisions and keyed
fingerprints unless a reviewed policy requires content.

## 4. Verify the backend

Local entrypoint smoke test:

```bash
uvicorn index:app --host 127.0.0.1 --port 8000
curl -i http://127.0.0.1:8000/health/live
```

Preview checks, replacing the host and secret:

```bash
curl -i https://YOUR_PREVIEW_HOST/health/live
curl -i https://YOUR_PREVIEW_HOST/health/ready
curl -i \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_SERVER_ONLY_KEY' \
  -H 'Idempotency-Key: deploy-smoke-001' \
  -d '{"message":"I am anxious about an interview result."}' \
  https://YOUR_PREVIEW_HOST/v1/classifications
```

Confirm that the response and platform logs contain the same `X-Request-ID`.
Then locate that request ID in LangSmith and verify that no secret appears in
trace inputs, outputs or metadata.

## 5. Deploy the frontend project

Import the same repository again and choose `web/` as the root directory. Add
the five backend/guest-protection values from `web/.env.example`. The frontend
requires the Upstash REST URL/token plus an independent
`GUEST_RATE_LIMIT_SECRET`; production guest requests fail closed without them.
Never expose `APP_API_KEY`, provider keys, Upstash credentials, or the guest
secret.

Keep the backend protected by its server-only API key. A guest-enabled frontend
must be reachable without login, so promote it only after health, anonymous
rate-limit, request-ID correlation, and provider-failure checks pass.

## Operational risks to watch

- Free NVIDIA endpoints can return `429` or `503`; low user count reduces but
  does not eliminate that risk.
- A cold instance must initialize dependencies and open the bundled vector
  file, so track cold-start latency separately from warm-request latency.
- One guidance request has several sequential provider calls. The backend
  function has a 120-second ceiling, but upstream timeouts should normally fail
  before that ceiling.
- Upstash is required for shared cache and idempotency across serverless
  instances and for guest rate limiting. In-memory state is not shared and can
  disappear at any time.
- Guest messages are intentionally page-session-only. They are still processed
  by configured model/observability providers under their retention policies.
