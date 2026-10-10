import { describe, expect, it } from "vitest";
import { speechTextForMessage } from "./speech";
import type { ChatMessage } from "./types";

describe("speechTextForMessage", () => {
  it("reads a regular assistant answer as written", () => {
    const message: ChatMessage = {
      id: "answer-1",
      role: "assistant",
      content: "A grounded answer [Bhagavad Gita 2.47].",
      createdAt: "2026-10-10T00:00:00.000Z",
    };

    expect(speechTextForMessage(message)).toBe("A grounded answer.");
  });

  it("turns a reflection card into a naturally ordered narration", () => {
    const message: ChatMessage = {
      id: "answer-2",
      role: "assistant",
      content: "",
      createdAt: "2026-10-10T00:00:00.000Z",
      reflection: {
        id: "focus",
        label: "Focus",
        type: "mind",
        krishnaSaid: "The mind can be gently returned.",
        howToOvercome: "Try one small attentive action.",
        verse: "6.26",
        sloka: "A short transliterated verse.",
        source: "live",
        reason: "generated",
      },
    };

    expect(speechTextForMessage(message)).toContain("What Krishna said. The mind can be gently returned.");
    expect(speechTextForMessage(message)).toContain("How to overcome. Try one small attentive action.");
    expect(speechTextForMessage(message)).not.toContain("Bhagavad Gita 6.26");
    expect(speechTextForMessage(message)).not.toContain("A short transliterated verse.");
  });
});
