import type { ChatMessage } from "@/lib/types";

export type GuidanceContext = {
  summary: string | null;
  recentTurns: Pick<ChatMessage, "role" | "content">[];
};

export type GuidanceErrorDetails = {
  stage?: string;
  failed_dimensions?: string[];
  scores?: Record<string, number>;
  fallback_trait?: string | null;
};

type BackendGuidanceResponse = {
  request_id: string;
  result: {
    guidance: string;
    citations: string[];
    presentation: {
      trait_id: string;
      label: string;
      what_krishna_said: string;
      how_to_overcome: string;
      verse: string;
      sloka: string;
    };
    model: string;
    faithfulness_probability: number;
    citation_coverage_probability: number;
    helpfulness_probability: number;
    agency_probability: number;
  };
  conversation: {
    schema_version: "1.0";
    summary: string | null;
    recent_turns: { role: "user" | "assistant"; content: string }[];
  };
  summary_updated: boolean;
  summary_deferred: boolean;
  summarized_turn_count: number;
};

export class GuidanceProxyError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
    readonly retryAfter?: string,
    readonly details?: GuidanceErrorDetails,
  ) {
    super(message);
  }
}

function backendUrl(path: string): string {
  const base = process.env.BACKEND_API_URL?.trim();
  if (!base) throw new GuidanceProxyError("The guidance service is not configured.", 503, "not_configured");
  return new URL(path, `${base.replace(/\/$/, "")}/`).toString();
}

export async function requestGuidance(input: {
  message: string;
  clientRequestId: string;
  idempotencyKey: string;
  context: GuidanceContext;
}): Promise<BackendGuidanceResponse> {
  const apiKey = process.env.APP_API_KEY?.trim();
  if (!apiKey) throw new GuidanceProxyError("The guidance service is not configured.", 503, "not_configured");

  const payload = {
    message: input.message,
    conversation: {
      schema_version: "1.0",
      summary: input.context.summary,
      recent_turns: input.context.recentTurns.map(({ role, content }) => ({
        role,
        content,
      })),
    },
  };

  let response: Response;
  try {
    response = await fetch(backendUrl("v1/guidance"), {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
        "X-Client-Request-ID": input.clientRequestId,
        "Idempotency-Key": input.idempotencyKey,
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(90_000),
    });
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    throw new GuidanceProxyError(
      timedOut ? "The guidance service took too long to respond." : "The guidance service is unavailable.",
      503,
      timedOut ? "upstream_timeout" : "upstream_unavailable",
    );
  }

  const body = (await response.json().catch(() => null)) as
    | BackendGuidanceResponse
    | { error?: { code?: string; message?: string; request_id?: string; details?: GuidanceErrorDetails } }
    | null;

  if (!response.ok) {
    const detail = body && "error" in body ? body.error : undefined;
    throw new GuidanceProxyError(
      detail?.message || "Guidance could not be generated safely.",
      response.status,
      detail?.code || "guidance_failed",
      detail?.request_id,
      response.headers.get("Retry-After") || undefined,
      detail?.details,
    );
  }

  if (
    !body ||
    !("result" in body) ||
    !body.result?.guidance ||
    !Array.isArray(body.result.citations) ||
    !body.result.presentation?.trait_id ||
    !body.result.presentation.what_krishna_said ||
    !body.result.presentation.how_to_overcome ||
    !body.result.presentation.verse ||
    !body.result.presentation.sloka ||
    !body.conversation ||
    !Array.isArray(body.conversation.recent_turns)
  ) {
    throw new GuidanceProxyError("The guidance service returned an invalid response.", 502, "invalid_upstream_response");
  }
  return body;
}
