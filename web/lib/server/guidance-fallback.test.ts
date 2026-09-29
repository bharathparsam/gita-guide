import { describe, expect, it } from "vitest";
import { GuidanceProxyError } from "./guidance";
import { createCuratedGuidanceFallback } from "./guidance-fallback";

describe("curated guidance fallback", () => {
  it("maps a helpfulness-only signal to the matching offline trait", () => {
    const result = createCuratedGuidanceFallback(new GuidanceProxyError(
      "Live guidance was safe but did not meet the helpfulness target.",
      422,
      "guidance_not_helpful",
      "request-123",
      undefined,
      {
        failed_dimensions: ["helpfulness"],
        fallback_trait: "purpose",
        scores: {
          faithfulness: 0.84,
          citation_coverage: 0.92,
          helpfulness: 0.73,
          agency: 0.89,
        },
      },
    ));

    expect(result?.requestId).toBe("request-123");
    expect(result?.message.reflection).toMatchObject({
      id: "purpose",
      source: "offline",
      reason: "service_fallback",
      verse: "18.46",
    });
    expect(result?.quality?.helpfulness).toBe(0.73);
  });

  it("does not soften hard grounding failures", () => {
    const result = createCuratedGuidanceFallback(new GuidanceProxyError(
      "Grounding failed",
      502,
      "guidance_failed",
    ));

    expect(result).toBeNull();
  });
});
