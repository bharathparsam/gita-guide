import { describe, expect, it } from "vitest";
import { recentContext, titleFromMessage } from "./conversations";
import type { ChatMessage } from "./types";

describe("conversation helpers", () => {
  it("normalizes and bounds generated titles", () => {
    expect(titleFromMessage("  I am   worried about tomorrow  ")).toBe("I am worried about tomorrow");
    expect(titleFromMessage("A".repeat(60))).toBe(`${"A".repeat(43)}…`);
  });

  it("passes only the eight most recent context messages", () => {
    const messages: ChatMessage[] = Array.from({ length: 10 }, (_, index) => ({
      id: String(index),
      role: index % 2 ? "assistant" : "user",
      content: `Message ${index}`,
      createdAt: "2026-01-01T00:00:00.000Z",
      citations: ["not forwarded"],
    }));
    const recent = recentContext(messages);
    expect(recent).toHaveLength(8);
    expect(recent[0].content).toBe("Message 2");
    expect(recent[0]).toEqual({ role: "user", content: "Message 2" });
  });
});
