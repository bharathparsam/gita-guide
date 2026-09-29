import { describe, expect, it } from "vitest";
import { parseGuestContext } from "./guest-context";

describe("parseGuestContext", () => {
  it("accepts bounded complete guest exchanges", () => {
    const result = parseGuestContext({
      summary: "  The user is waiting for an outcome.  ",
      recentTurns: [
        { role: "user", content: " I finished the interview. " },
        { role: "assistant", content: " Focus on the action you can take now. " },
      ],
    });

    expect(result).toEqual({
      ok: true,
      value: {
        summary: "The user is waiting for an outcome.",
        recentTurns: [
          { role: "user", content: "I finished the interview." },
          { role: "assistant", content: "Focus on the action you can take now." },
        ],
      },
    });
  });

  it("accepts a new guest conversation", () => {
    expect(parseGuestContext({ summary: null, recentTurns: [] })).toEqual({
      ok: true,
      value: { summary: null, recentTurns: [] },
    });
  });

  it.each([
    [{ summary: null, recentTurns: [{ role: "assistant", content: "Wrong first role" }] }],
    [{ summary: null, recentTurns: [{ role: "user", content: "Incomplete exchange" }] }],
    [{ summary: null, recentTurns: [{ role: "user", content: "" }, { role: "assistant", content: "Reply" }] }],
    [{ summary: "x".repeat(2_001), recentTurns: [] }],
  ])("rejects malformed or oversized context", (context) => {
    expect(parseGuestContext(context).ok).toBe(false);
  });
});
