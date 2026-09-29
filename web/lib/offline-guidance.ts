import { gitaTraits } from "./traits-dataset";
import type {
  ChatMessage,
  TraitExplanation,
  TraitReflection,
  TraitType,
} from "./types";

export const TRAIT_TYPES: readonly { id: TraitType; label: string }[] = [
  { id: "emotion", label: "Emotions" },
  { id: "mind", label: "Mind" },
  { id: "desire", label: "Desires" },
  { id: "work", label: "Work & purpose" },
  { id: "habit", label: "Habits" },
  { id: "relationship", label: "Relationships" },
  { id: "virtue", label: "Virtues" },
  { id: "ego", label: "Ego" },
  { id: "material", label: "Material life" },
  { id: "adversity", label: "Adversity" },
] as const;

export type OfflineSafetyDecision =
  | { action: "allow" }
  | { action: "block"; message: string }
  | { action: "escalate"; message: string };

const CRISIS_PATTERNS = [
  /\b(?:kill|hurt)\s+myself\b/i,
  /\bend\s+my\s+life\b/i,
  /\b(?:suicide|suicidal)\b/i,
];

const EXPLICIT_PATTERNS = [
  /\bf[\W_]*u[\W_]*c[\W_]*k(?:ing|ed|er|s)?\b/i,
  /\bf[\W_]{2,}(?:ing|ed|er|s)?\b/i,
  /\bc[\W_]*u[\W_]*n[\W_]*t(?:s)?\b/i,
  /\bp[\W_]*o[\W_]*r[\W_]*n(?:ography|ographic)?\b/i,
  /\b(?:graphic|explicit)\s+sexual\s+(?:content|description|material)\b/i,
];

function normalize(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("en")
    .replace(/[_’']/g, " ")
    .replace(/[^a-z0-9\s-]/g, " ")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function stem(token: string): string {
  if (token.startsWith("compar")) return "compar";
  if (token.length > 4 && token.endsWith("ied")) return `${token.slice(0, -3)}y`;
  if (token.length > 5 && token.endsWith("ing")) return token.slice(0, -3);
  if (token.length > 4 && token.endsWith("ed")) return token.slice(0, -2);
  if (token.length > 4 && token.endsWith("s")) return token.slice(0, -1);
  return token;
}

function containsPhrase(message: string, phrase: string): boolean {
  return ` ${message} `.includes(` ${phrase} `);
}

function traitScore(message: string, trait: TraitExplanation): number {
  const tokens = new Set(message.split(" ").filter(Boolean).map(stem));
  const canonical = [trait.id, trait.label].map(normalize);
  let score = 0;

  for (const phrase of canonical) {
    if (!phrase) continue;
    if (containsPhrase(message, phrase)) {
      score = Math.max(score, 100 + phrase.split(" ").length * 8);
    }
    const phraseTokens = phrase.split(" ").map(stem);
    if (phraseTokens.every((token) => tokens.has(token))) {
      score = Math.max(score, 86 + phraseTokens.length * 6);
    }
  }

  for (const alias of trait.aliases) {
    const phrase = normalize(alias);
    if (phrase && containsPhrase(message, phrase)) {
      score = Math.max(score, 58 + phrase.split(" ").length * 7);
    }
  }
  return score;
}

export function evaluateOfflineSafety(message: string): OfflineSafetyDecision {
  if (CRISIS_PATTERNS.some((pattern) => pattern.test(message))) {
    return {
      action: "escalate",
      message:
        "Offline reflections are not appropriate for a message that may involve immediate self-harm risk. Please contact local emergency services or a trusted person who can stay with you now.",
    };
  }
  if (EXPLICIT_PATTERNS.some((pattern) => pattern.test(message))) {
    return {
      action: "block",
      message: "This message cannot be processed under the offline input policy.",
    };
  }
  return { action: "allow" };
}

export function classifyOfflineTrait(message: string): TraitExplanation | null {
  const normalized = normalize(message);
  if (!normalized) return null;
  const ranked = gitaTraits
    .map((trait, index) => ({ trait, index, score: traitScore(normalized, trait) }))
    .filter(({ score }) => score >= 58)
    .sort((left, right) => right.score - left.score || left.index - right.index);
  return ranked[0]?.trait || null;
}

/** Returns the locally curated traits matching both the selected type and every search term. */
export function searchOfflineTraits(
  query: string,
  type: TraitType | "all" = "all",
): readonly TraitExplanation[] {
  const normalizedQuery = normalize(query);
  return gitaTraits.filter((trait) => {
    if (type !== "all" && trait.type !== type) return false;
    if (!normalizedQuery) return true;
    const searchable = [trait.id, trait.label, ...trait.aliases]
      .map(normalize)
      .join(" ");
    return normalizedQuery
      .split(" ")
      .filter(Boolean)
      .every((term) => searchable.includes(term));
  });
}

export function createOfflineReflectionForTrait(
  traitId: string,
  reason: TraitReflection["reason"] = "chosen",
): ChatMessage | null {
  const trait = gitaTraits.find(({ id }) => id === traitId);
  return trait ? createReflectionMessage(trait, reason) : null;
}

function createReflectionMessage(
  trait: TraitExplanation,
  reason: TraitReflection["reason"],
): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role: "assistant",
    content:
      reason === "chosen"
        ? "Here is a curated reflection from the offline guide."
        : "The live guidance service was unavailable, so here is a curated offline reflection.",
    citations: [`Bhagavad Gita ${trait.verse}`],
    createdAt: new Date().toISOString(),
    reflection: {
      id: trait.id,
      label: trait.label,
      type: trait.type,
      krishnaSaid: trait.krishnaSaid,
      howToOvercome: trait.howToOvercome,
      verse: trait.verse,
      sloka: trait.sloka,
      source: "offline",
      reason,
    },
  };
}

export function createOfflineReflection(
  message: string,
  reason: TraitReflection["reason"],
): ChatMessage | null {
  const trait = classifyOfflineTrait(message);
  if (!trait) return null;
  return createReflectionMessage(trait, reason);
}
