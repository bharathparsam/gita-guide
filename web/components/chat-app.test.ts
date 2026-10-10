import { describe, expect, it } from "vitest";
import { ChatRequestError, friendlyFailure } from "../lib/failure-guidance";

describe("chat failure guidance", () => {
  it("turns safety blocks into calm policy guidance without exposing a request id", () => {
    const result = friendlyFailure(new ChatRequestError(
      "This message cannot be processed under the input safety policy.",
      422,
      "input_blocked",
      "internal-request-id",
    ));

    expect(result.action).toBeNull();
    expect(result.message).toContain("steered the chariot outside this guide’s safety boundaries");
    expect(result.message).not.toContain("internal-request-id");
  });

  it("offers the curated traits when no grounded evidence is available", () => {
    const result = friendlyFailure(new ChatRequestError(
      "No sufficiently grounded passages were available.",
      422,
      "insufficient_evidence",
      "internal-request-id",
    ));

    expect(result.action).toBe("browse");
    expect(result.message).toContain("curated traits");
  });
});
