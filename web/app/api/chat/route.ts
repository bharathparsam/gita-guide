import { NextResponse } from "next/server";
import {
  ensureConversation,
  findCompletedRequest,
  loadContext,
  persistExchange,
} from "@/lib/server/history";
import { GuidanceProxyError, requestGuidance, type GuidanceContext } from "@/lib/server/guidance";
import { hasSupabaseAuthCookie } from "@/lib/server/auth-cookie";
import { parseGuestContext } from "@/lib/server/guest-context";
import { limitGuestRequest } from "@/lib/server/guest-rate-limit";
import { titleFromMessage } from "@/lib/conversations";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";
import { gitaTraits } from "@/lib/traits-dataset";
import { createCuratedGuidanceFallback } from "@/lib/server/guidance-fallback";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type IncomingBody = {
  message?: unknown;
  conversationId?: unknown;
  clientRequestId?: unknown;
  guestContext?: unknown;
};

type GuidanceResponse = Awaited<ReturnType<typeof requestGuidance>>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const INLINE_CITATION = /\s*\[Bhagavad Gita\s+\d{1,2}\.\d{1,3}(?:-\d{1,3})?\]/g;

function invalid(message: string) {
  return NextResponse.json(
    { error: { code: "invalid_request", message } },
    { status: 400, headers: { "Cache-Control": "private, no-store" } },
  );
}

function formatGuidance(guidance: GuidanceResponse) {
  const presentation = guidance.result.presentation;
  const trait = gitaTraits.find(({ id }) => id === presentation.trait_id);
  const message = {
    id: crypto.randomUUID(),
    role: "assistant" as const,
    content: guidance.result.guidance,
    citations: guidance.result.citations,
    requestId: guidance.request_id,
    createdAt: new Date().toISOString(),
    ...(trait ? {
      reflection: {
        id: trait.id,
        label: presentation.label,
        type: trait.type,
        krishnaSaid: presentation.what_krishna_said.replace(INLINE_CITATION, "").trim(),
        howToOvercome: presentation.how_to_overcome,
        verse: presentation.verse,
        sloka: presentation.sloka,
        source: "live" as const,
        reason: "generated" as const,
      },
    } : {}),
  };
  return {
    message,
    quality: {
      faithfulness: guidance.result.faithfulness_probability,
      citationCoverage: guidance.result.citation_coverage_probability,
      helpfulness: guidance.result.helpfulness_probability,
      agency: guidance.result.agency_probability,
    },
    memory: {
      summary: guidance.conversation.summary,
      recentTurns: guidance.conversation.recent_turns,
      summaryUpdated: guidance.summary_updated,
      summaryDeferred: guidance.summary_deferred,
      summarizedTurnCount: guidance.summarized_turn_count,
    },
  };
}

function failureResponse(caught: unknown) {
  const failure =
    caught instanceof GuidanceProxyError
      ? caught
      : new GuidanceProxyError(
          "Conversation history or guidance is temporarily unavailable.",
          503,
          "service_unavailable",
        );
  return NextResponse.json(
    {
      error: {
        code: failure.code,
        message: failure.message,
        requestId: failure.requestId,
        ...(process.env.NODE_ENV !== "production" && failure.details
          ? { details: failure.details }
          : {}),
      },
    },
    {
      status: failure.status,
      headers: {
        "Cache-Control": "private, no-store",
        ...(failure.retryAfter ? { "Retry-After": failure.retryAfter } : {}),
      },
    },
  );
}

function helpfulnessFallbackResponse(
  caught: unknown,
  context: GuidanceContext,
) {
  const fallback = createCuratedGuidanceFallback(caught);
  if (!fallback) return null;
  const { message } = fallback;
  const failure = caught as GuidanceProxyError;
  console.warn(JSON.stringify({
    event: "guidance.curated_fallback",
    requestId: failure.requestId,
    failedDimensions: failure.details?.failed_dimensions,
    scores: failure.details?.scores,
    fallbackTrait: message.reflection?.id,
  }));
  return NextResponse.json(
    {
      requestId: fallback.requestId || message.id,
      message,
      memory: {
        summary: context.summary,
        recentTurns: context.recentTurns,
        summaryUpdated: false,
        summaryDeferred: false,
      },
      quality: fallback.quality,
    },
    {
      headers: {
        "Cache-Control": "private, no-store",
        ...(fallback.requestId ? { "X-Request-ID": fallback.requestId } : {}),
        "X-Guidance-Fallback": "curated-offline",
      },
    },
  );
}

async function authenticatedUserId(request: Request): Promise<string | null> {
  if (!hasSupabaseAuthCookie(request.headers.get("cookie"))) return null;
  try {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getUser();
    return error ? null : data.user?.id || null;
  } catch {
    return null;
  }
}

async function guestResponse(request: Request, input: {
  message: string;
  conversationId: string;
  clientRequestId: string;
  context: GuidanceContext;
}) {
  const rateLimit = await limitGuestRequest(request);
  if (!rateLimit.allowed) {
    const retryAfter = rateLimit.reset
      ? Math.max(1, Math.ceil((rateLimit.reset - Date.now()) / 1_000)).toString()
      : undefined;
    return NextResponse.json(
      { error: { code: rateLimit.status === 429 ? "rate_limited" : "guest_unavailable", message: rateLimit.message } },
      {
        status: rateLimit.status,
        headers: {
          "Cache-Control": "private, no-store",
          ...(retryAfter ? { "Retry-After": retryAfter } : {}),
        },
      },
    );
  }

  const guidance = await requestGuidance({
    message: input.message,
    clientRequestId: input.clientRequestId,
    idempotencyKey: `guest:${input.conversationId}:${input.clientRequestId}`,
    context: input.context,
  });
  const result = formatGuidance(guidance);
  return NextResponse.json(
    { requestId: guidance.request_id, ...result },
    {
      headers: {
        "Cache-Control": "private, no-store",
        "X-Request-ID": guidance.request_id,
        ...(rateLimit.remaining === undefined ? {} : { "X-RateLimit-Remaining": rateLimit.remaining.toString() }),
        ...(rateLimit.reset === undefined ? {} : { "X-RateLimit-Reset": rateLimit.reset.toString() }),
      },
    },
  );
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as IncomingBody | null;
  if (!body || typeof body.message !== "string") {
    return invalid("Enter a message to continue.");
  }
  const message = body.message.trim();
  if (!message || message.length > 4_000) {
    return invalid("Messages must contain 1–4,000 characters.");
  }
  if (typeof body.conversationId !== "string" || !UUID.test(body.conversationId)) {
    return invalid("A valid conversation is required.");
  }
  if (typeof body.clientRequestId !== "string" || !UUID.test(body.clientRequestId)) {
    return invalid("A valid client request ID is required.");
  }

  const userId = await authenticatedUserId(request);
  if (!userId) {
    const context = parseGuestContext(body.guestContext);
    if (!context.ok) return invalid(context.message);
    try {
      return await guestResponse(request, {
        message,
        conversationId: body.conversationId,
        clientRequestId: body.clientRequestId,
        context: context.value,
      });
    } catch (caught) {
      const fallback = helpfulnessFallbackResponse(caught, context.value);
      if (fallback) return fallback;
      return failureResponse(caught);
    }
  }

  let fallbackContext: GuidanceContext = { summary: null, recentTurns: [] };
  try {
    const admin = createAdminClient();
    await ensureConversation(admin, {
      conversationId: body.conversationId,
      userId,
      title: titleFromMessage(message),
    });

    const prior = await findCompletedRequest(admin, userId, body.clientRequestId);
    if (prior) {
      return NextResponse.json(
        {
          requestId: prior.requestId,
          message: prior,
          memory: {
            summary: null,
            recentTurns: [],
            summaryUpdated: false,
            summaryDeferred: false,
          },
        },
        {
          headers: {
            "Cache-Control": "private, no-store",
            ...(prior.requestId ? { "X-Request-ID": prior.requestId } : {}),
          },
        },
      );
    }

    const contextBefore = await loadContext(admin, userId, body.conversationId);
    fallbackContext = {
      summary: contextBefore.summary,
      recentTurns: contextBefore.recentTurns,
    };
    const guidance = await requestGuidance({
      message,
      clientRequestId: body.clientRequestId,
      idempotencyKey: `web:${userId}:${body.conversationId}:${body.clientRequestId}`,
      context: {
        summary: contextBefore.summary,
        recentTurns: contextBefore.recentTurns,
      },
    });
    const result = formatGuidance(guidance);
    await persistExchange(admin, {
      userId,
      conversationId: body.conversationId,
      clientMessageId: body.clientRequestId,
      userContent: message,
      assistantMessage: result.message,
      model: guidance.result.model || "configured-generation-model",
      quality: result.quality,
      contextBefore,
      memory: result.memory,
    });

    return NextResponse.json(
      { requestId: guidance.request_id, ...result },
      {
        headers: {
          "Cache-Control": "private, no-store",
          "X-Request-ID": guidance.request_id,
        },
      },
    );
  } catch (caught) {
    const fallback = helpfulnessFallbackResponse(caught, fallbackContext);
    if (fallback) return fallback;
    return failureResponse(caught);
  }
}
