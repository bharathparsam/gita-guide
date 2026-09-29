import type { ChatMessage, Conversation, ConversationTurn } from "./types";

export function createConversation(): Conversation {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: "New reflection",
    createdAt: now,
    updatedAt: now,
    summary: null,
    recentTurns: [],
    messages: [],
  };
}

export function titleFromMessage(message: string): string {
  const normalized = message.replace(/\s+/g, " ").trim();
  if (normalized.length <= 46) return normalized || "New reflection";
  return `${normalized.slice(0, 43).trimEnd()}…`;
}

export function recentContext(messages: ChatMessage[]): ConversationTurn[] {
  return messages.slice(-8).map(({ role, content }) => ({ role, content }));
}
