import type { SupabaseClient } from "@supabase/supabase-js";
import type { ChatMessage, Conversation, ConversationTurn, TraitReflection } from "@/lib/types";

const MAX_CONTEXT_TURNS = 8;
const MAX_CONTEXT_CHARS = 2_000;

type MessageRow = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  request_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

type SummaryRow = {
  through_message_id: string;
  revision: number;
  source_message_count: number;
  summary: string;
};

export type StoredContext = {
  summary: string | null;
  recentTurns: ConversationTurn[];
  turnRows: MessageRow[];
  latestSummary: SummaryRow | null;
};

function storageError(operation: string, error: { message: string } | null): never {
  throw new Error(`${operation} failed${error ? `: ${error.message}` : ""}`);
}

function citations(metadata: Record<string, unknown> | null): string[] | undefined {
  const value = metadata?.citations;
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? value
    : undefined;
}

function reflection(metadata: Record<string, unknown> | null): TraitReflection | undefined {
  const value = metadata?.reflection;
  if (!value || typeof value !== "object") return undefined;
  const candidate = value as Record<string, unknown>;
  const required = ["id", "label", "type", "krishnaSaid", "howToOvercome", "verse", "sloka", "source", "reason"];
  const validTypes = new Set(["emotion", "mind", "desire", "work", "habit", "relationship", "virtue", "ego", "material", "adversity"]);
  const validSources = new Set(["offline", "live"]);
  const validReasons = new Set(["chosen", "service_fallback", "generated"]);
  return required.every((key) => typeof candidate[key] === "string")
    && validTypes.has(String(candidate.type))
    && validSources.has(String(candidate.source))
    && validReasons.has(String(candidate.reason))
    ? candidate as TraitReflection
    : undefined;
}

function completeExchanges(rows: MessageRow[]): MessageRow[] {
  const result: MessageRow[] = [];
  for (let index = 0; index + 1 < rows.length; index += 1) {
    const first = rows[index];
    const second = rows[index + 1];
    if (first.role === "user" && second.role === "assistant") {
      result.push(first, second);
      index += 1;
    }
  }
  return result.slice(-MAX_CONTEXT_TURNS);
}

export async function listConversations(
  admin: SupabaseClient,
  userId: string,
): Promise<Conversation[]> {
  const { data: conversationRows, error: conversationError } = await admin
    .from("conversations")
    .select("id,title,created_at,updated_at")
    .eq("owner_id", userId)
    .order("updated_at", { ascending: false })
    .limit(30);
  if (conversationError) storageError("Loading conversations", conversationError);
  if (!conversationRows?.length) return [];

  const ids = conversationRows.map((row) => row.id);
  const { data: messageRows, error: messageError } = await admin
    .from("messages")
    .select("id,conversation_id,role,content,request_id,metadata,created_at")
    .eq("owner_id", userId)
    .in("conversation_id", ids)
    .in("role", ["user", "assistant"])
    .order("created_at", { ascending: true });
  if (messageError) storageError("Loading messages", messageError);

  const grouped = new Map<string, ChatMessage[]>();
  for (const raw of messageRows || []) {
    const row = raw as MessageRow;
    const messages = grouped.get(row.conversation_id) || [];
    messages.push({
      id: row.id,
      role: row.role,
      content: row.content,
      requestId: row.request_id || undefined,
      citations: citations(row.metadata),
      reflection: reflection(row.metadata),
      createdAt: row.created_at,
    });
    grouped.set(row.conversation_id, messages);
  }

  return conversationRows.map((row) => {
    const messages = grouped.get(row.id) || [];
    return {
      id: row.id,
      title: row.title || "New reflection",
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      summary: null,
      recentTurns: messages.slice(-MAX_CONTEXT_TURNS).map(({ role, content }) => ({
        role,
        content: content.slice(0, MAX_CONTEXT_CHARS),
      })),
      messages,
    };
  });
}

export async function ensureConversation(
  admin: SupabaseClient,
  input: { conversationId: string; userId: string; title: string },
): Promise<void> {
  const { data, error } = await admin
    .from("conversations")
    .select("id")
    .eq("id", input.conversationId)
    .eq("owner_id", input.userId)
    .maybeSingle();
  if (error) storageError("Checking conversation ownership", error);
  if (data) return;

  const { error: insertError } = await admin.from("conversations").insert({
    id: input.conversationId,
    owner_id: input.userId,
    title: input.title,
  });
  if (insertError) storageError("Creating conversation", insertError);
}

export async function loadContext(
  admin: SupabaseClient,
  userId: string,
  conversationId: string,
): Promise<StoredContext> {
  const [{ data: summaryRows, error: summaryError }, { data: rawRows, error: messageError }] =
    await Promise.all([
      admin
        .from("conversation_summaries")
        .select("through_message_id,revision,source_message_count,summary")
        .eq("owner_id", userId)
        .eq("conversation_id", conversationId)
        .order("revision", { ascending: false })
        .limit(1),
      admin
        .from("messages")
        .select("id,conversation_id,role,content,request_id,metadata,created_at")
        .eq("owner_id", userId)
        .eq("conversation_id", conversationId)
        .in("role", ["user", "assistant"])
        .order("created_at", { ascending: false })
        .limit(MAX_CONTEXT_TURNS),
    ]);
  if (summaryError) storageError("Loading conversation summary", summaryError);
  if (messageError) storageError("Loading conversation context", messageError);

  const latestSummary = (summaryRows?.[0] as SummaryRow | undefined) || null;
  let rows = ((rawRows || []) as MessageRow[]).reverse();
  if (latestSummary) {
    const summaryBoundary = rows.findIndex(
      (row) => row.id === latestSummary.through_message_id,
    );
    if (summaryBoundary >= 0) rows = rows.slice(summaryBoundary + 1);
  }
  rows = completeExchanges(rows);
  return {
    summary: latestSummary?.summary || null,
    recentTurns: rows.map(({ role, content }) => ({
      role,
      content: content.slice(0, MAX_CONTEXT_CHARS),
    })),
    turnRows: rows,
    latestSummary,
  };
}

export async function findCompletedRequest(
  admin: SupabaseClient,
  userId: string,
  clientMessageId: string,
): Promise<ChatMessage | null> {
  const { data: userMessage, error } = await admin
    .from("messages")
    .select("request_id")
    .eq("owner_id", userId)
    .eq("id", clientMessageId)
    .eq("role", "user")
    .maybeSingle();
  if (error) storageError("Checking message idempotency", error);
  if (!userMessage?.request_id) return null;
  const { data: assistant, error: assistantError } = await admin
    .from("messages")
    .select("id,role,content,request_id,metadata,created_at")
    .eq("owner_id", userId)
    .eq("request_id", userMessage.request_id)
    .eq("role", "assistant")
    .maybeSingle();
  if (assistantError) storageError("Loading prior response", assistantError);
  if (!assistant) return null;
  return {
    id: assistant.id,
    role: "assistant",
    content: assistant.content,
    requestId: assistant.request_id || undefined,
    citations: citations(assistant.metadata as Record<string, unknown> | null),
    reflection: reflection(assistant.metadata as Record<string, unknown> | null),
    createdAt: assistant.created_at,
  };
}

export async function persistExchange(
  admin: SupabaseClient,
  input: {
    userId: string;
    conversationId: string;
    clientMessageId: string;
    userContent: string;
    assistantMessage: ChatMessage;
    model: string;
    quality: Record<string, number>;
    contextBefore: StoredContext;
    memory: {
      summary: string | null;
      recentTurns: ConversationTurn[];
      summaryUpdated: boolean;
      summarizedTurnCount: number;
    };
  },
): Promise<void> {
  const requestId = input.assistantMessage.requestId;
  const assistantId = input.assistantMessage.id;
  const { error: messagesError } = await admin.from("messages").insert([
    {
      id: input.clientMessageId,
      conversation_id: input.conversationId,
      owner_id: input.userId,
      role: "user",
      content: input.userContent,
      request_id: requestId,
      client_message_id: input.clientMessageId,
    },
    {
      id: assistantId,
      conversation_id: input.conversationId,
      owner_id: input.userId,
      role: "assistant",
      content: input.assistantMessage.content,
      request_id: requestId,
      model: input.model,
      metadata: {
        citations: input.assistantMessage.citations || [],
        reflection: input.assistantMessage.reflection,
        quality: input.quality,
      },
    },
  ]);
  if (messagesError) storageError("Saving conversation messages", messagesError);

  if (!input.memory.summaryUpdated || !input.memory.summary) return;
  const combinedIds = [
    ...input.contextBefore.turnRows.map((row) => row.id),
    input.clientMessageId,
    assistantId,
  ];
  const summarizedTurnCount = input.memory.summarizedTurnCount;
  const throughMessageId = combinedIds[summarizedTurnCount - 1];
  if (!throughMessageId) storageError("Resolving summary boundary", null);
  const { error: summaryError } = await admin.from("conversation_summaries").insert({
    conversation_id: input.conversationId,
    owner_id: input.userId,
    through_message_id: throughMessageId,
    revision: (input.contextBefore.latestSummary?.revision || 0) + 1,
    source_message_count:
      (input.contextBefore.latestSummary?.source_message_count || 0) + summarizedTurnCount,
    summary: input.memory.summary,
    model: input.model,
    prompt_version: "conversation-summary-v1",
  });
  if (summaryError) storageError("Saving conversation summary", summaryError);
}
