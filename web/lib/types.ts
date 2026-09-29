export type Citation = string;

export type TraitType =
  | "emotion"
  | "mind"
  | "desire"
  | "work"
  | "habit"
  | "relationship"
  | "virtue"
  | "ego"
  | "material"
  | "adversity";

export type TraitExplanation = {
  id: string;
  label: string;
  type: TraitType;
  aliases: readonly string[];
  krishnaSaid: string;
  howToOvercome: string;
  verse: string;
  sloka: string;
};

export type TraitReflection = Omit<TraitExplanation, "aliases"> & {
  source: "offline" | "live";
  reason: "chosen" | "service_fallback" | "generated";
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  citations?: Citation[];
  requestId?: string;
  reflection?: TraitReflection;
};

export type ConversationTurn = Pick<ChatMessage, "role" | "content">;

export type Conversation = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  summary: string | null;
  recentTurns: ConversationTurn[];
  messages: ChatMessage[];
};

export type ChatApiResult = {
  message: ChatMessage;
  requestId: string;
  memory: {
    summary: string | null;
    recentTurns: ConversationTurn[];
    summaryUpdated: boolean;
    summaryDeferred: boolean;
  };
  quality?: {
    faithfulness: number;
    citationCoverage: number;
    helpfulness: number;
    agency: number;
  };
};
