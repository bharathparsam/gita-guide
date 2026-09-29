import { createOfflineReflectionForTrait } from "../offline-guidance";
import type { ChatMessage, ChatApiResult } from "../types";
import { GuidanceProxyError } from "./guidance";

export type CuratedGuidanceFallback = {
  message: ChatMessage;
  requestId?: string;
  quality?: ChatApiResult["quality"];
};

export function createCuratedGuidanceFallback(
  caught: unknown,
): CuratedGuidanceFallback | null {
  if (!(caught instanceof GuidanceProxyError) || caught.code !== "guidance_not_helpful") {
    return null;
  }
  const traitId = caught.details?.fallback_trait;
  if (typeof traitId !== "string") return null;
  const message = createOfflineReflectionForTrait(traitId, "service_fallback");
  if (!message) return null;
  message.requestId = caught.requestId;
  const scores = caught.details?.scores;
  return {
    message,
    requestId: caught.requestId,
    ...(scores ? {
      quality: {
        faithfulness: scores.faithfulness,
        citationCoverage: scores.citation_coverage,
        helpfulness: scores.helpfulness,
        agency: scores.agency,
      },
    } : {}),
  };
}
