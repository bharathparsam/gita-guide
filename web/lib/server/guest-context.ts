import type { GuidanceContext } from "@/lib/server/guidance";

const MAX_SUMMARY_LENGTH = 2_000;
const MAX_TURNS = 8;
const MAX_TURN_LENGTH = 2_000;

export type GuestContextResult =
  | { ok: true; value: GuidanceContext }
  | { ok: false; message: string };

export function parseGuestContext(input: unknown): GuestContextResult {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return { ok: false, message: "Guest conversation context is required." };
  }
  const candidate = input as { summary?: unknown; recentTurns?: unknown };
  if (candidate.summary !== null && typeof candidate.summary !== "string") {
    return { ok: false, message: "Guest conversation summary is invalid." };
  }
  const summary = typeof candidate.summary === "string" ? candidate.summary.trim() : null;
  if (summary && summary.length > MAX_SUMMARY_LENGTH) {
    return { ok: false, message: "Guest conversation summary is too long." };
  }
  if (!Array.isArray(candidate.recentTurns) || candidate.recentTurns.length > MAX_TURNS) {
    return { ok: false, message: "Guest conversation turns are invalid." };
  }
  if (candidate.recentTurns.length % 2 !== 0) {
    return { ok: false, message: "Guest conversation turns must contain complete exchanges." };
  }

  const recentTurns: GuidanceContext["recentTurns"] = [];
  for (let index = 0; index < candidate.recentTurns.length; index += 1) {
    const turn = candidate.recentTurns[index];
    const expectedRole = index % 2 === 0 ? "user" : "assistant";
    if (!turn || typeof turn !== "object" || Array.isArray(turn)) {
      return { ok: false, message: "Guest conversation contains an invalid turn." };
    }
    const { role, content } = turn as { role?: unknown; content?: unknown };
    if (role !== expectedRole || typeof content !== "string") {
      return { ok: false, message: "Guest conversation turns must alternate between user and assistant." };
    }
    const normalizedContent = content.trim();
    if (!normalizedContent || normalizedContent.length > MAX_TURN_LENGTH) {
      return { ok: false, message: "Guest conversation contains invalid turn content." };
    }
    recentTurns.push({ role: expectedRole, content: normalizedContent });
  }

  return { ok: true, value: { summary: summary || null, recentTurns } };
}
