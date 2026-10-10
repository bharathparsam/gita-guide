export const OFFLINE_FALLBACK_CODES = new Set([
  "guidance_not_eligible",
  "insufficient_evidence",
  "guidance_failed",
  "guidance_not_helpful",
  "generation_service_unavailable",
  "upstream_timeout",
  "upstream_unavailable",
  "invalid_upstream_response",
  "not_configured",
  "service_unavailable",
]);

export type RecoveryAction = "retry" | "browse" | null;

export class ChatRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    readonly requestId?: string,
  ) {
    super(message);
  }
}

export function friendlyFailure(caught: unknown): { message: string; action: RecoveryAction } {
  if (!(caught instanceof ChatRequestError)) {
    return {
      message: "The live guide is unavailable right now. You can still explore a curated reflection.",
      action: "browse",
    };
  }
  if (caught.code === "input_blocked") {
    return {
      message: "That request has steered the chariot outside this guide’s safety boundaries. Let’s bring it back to the road—you can rephrase it around the feeling, choice, or situation behind it.",
      action: null,
    };
  }
  if (caught.code === "safety_escalation") {
    return { message: caught.message, action: null };
  }
  if (caught.code === "guidance_not_eligible" || caught.code === "insufficient_evidence") {
    return {
      message: "I’m sorry—I couldn’t find passages strong enough to ground a trustworthy answer. You can explore the curated traits and choose the reflection that feels closest.",
      action: "browse",
    };
  }
  if (caught.code === "rate_limited" || caught.code === "idempotency_in_progress") {
    return {
      message: "The guide needs a brief pause before trying again.",
      action: "retry",
    };
  }
  if (OFFLINE_FALLBACK_CODES.has(caught.code || "")) {
    return {
      message: "The live guide couldn’t complete this reflection safely. You can continue with the curated offline traits instead.",
      action: "browse",
    };
  }
  return { message: caught.message || "Something went wrong. Please try again.", action: "retry" };
}
