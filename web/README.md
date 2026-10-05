# Gita Guide web

The Next.js frontend opens directly into a responsive guest-only chat. Its
server-only `/api/chat` route forwards requests to the Python `/v1/guidance`
endpoint without exposing `APP_API_KEY` to the browser. Conversations live only
in React state and are cleared when the page refreshes.
While a request is pending, the chat keeps its layout stable and announces bounded,
accessible progress messages for understanding, retrieval, drafting, and final
grounding/safety checks. These are elapsed-time indicators rather than server-streamed
stage events; the final answer is shown only after all mandatory checks pass.

The composer also offers an explicit **Offline guide** mode. It performs deterministic
local matching against the typed 78-entry trait catalog and renders the matched label,
trait category, curated explanation, practical reflection, Sanskrit sloka, and verse.
Opening the mode displays all traits as accessible buttons, with category filters and
a search field that also matches curated aliases; selecting a trait renders its
reflection immediately without sending a request to the live guidance API.
It makes no provider call and does not persist the exchange. The same local response is
used as a clearly disclosed fallback for retryable live-generation failures, but never
for backend safety rejections, safety-service failures, authorization failures, or
abuse-rate-limit responses. Local crisis and explicit-language checks run before every
offline match. This is a provider-free mode inside the loaded web application, not yet
a service-worker/PWA guarantee that the site can be opened with no network connection.

## Local setup

```bash
cp .env.example .env.local
npm install
npm run dev
```

The Python API must also be running and its guidance release flags enabled. In
development only, guest requests can run without
Upstash rate-limit variables; production fails guest requests closed unless all
three guest abuse-protection variables are configured.

Rolling memory lives only in React state and disappears on refresh; it is never
written to a database or browser storage. The memory payload is schema-validated
and bounded before it reaches the Python service. The browser never receives the
Redis token or Python API key.

## Deploy

Set the five backend/guest-protection values from `.env.example` in Vercel.
`APP_API_KEY`, `BACKEND_API_URL`, all Upstash values, and
`GUEST_RATE_LIMIT_SECRET` are server-only.

```bash
npm test
npm run build
```
