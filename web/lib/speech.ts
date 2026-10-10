import type { ChatMessage } from "@/lib/types";

const INLINE_CITATION = /\s*\[Bhagavad Gita\s+\d{1,2}\.\d{1,3}(?:-\d{1,3})?\]/gi;

export function speechTextForMessage(message: ChatMessage): string {
  if (!message.reflection) return message.content.replace(INLINE_CITATION, "").trim();

  const reflection = message.reflection;
  return [
    `What Krishna said. ${reflection.krishnaSaid}`,
    `How to overcome. ${reflection.howToOvercome}`,
  ].join("\n\n");
}
