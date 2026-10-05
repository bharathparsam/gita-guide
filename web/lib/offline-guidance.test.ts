import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { gitaTraits } from "./traits-dataset";
import {
  classifyOfflineTrait,
  createOfflineReflection,
  createOfflineReflectionForTrait,
  evaluateOfflineSafety,
  searchOfflineTraits,
  TRAIT_TYPES,
} from "./offline-guidance";

describe("offline guidance", () => {
  it("keeps the curated dataset structurally complete and unique", () => {
    expect(gitaTraits).toHaveLength(78);
    expect(new Set(gitaTraits.map(({ id }) => id)).size).toBe(gitaTraits.length);
    for (const trait of gitaTraits) {
      expect(trait.label.trim()).not.toBe("");
      expect(trait.krishnaSaid.trim()).not.toBe("");
      expect(trait.howToOvercome.trim()).not.toBe("");
      expect(trait.verse).toMatch(/^\d{1,2}\.\d{1,3}$/);
      expect(trait.sloka.trim().split("\n").length).toBeGreaterThanOrEqual(2);
    }
  });

  it("references verses that exist in the local Bhagavad Gita corpus", () => {
    const corpus = readFileSync(
      new URL("../../data/processed/gita_chunks.jsonl", import.meta.url),
      "utf8",
    )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as { chapter: number; verse_start: number; verse_end: number });

    for (const trait of gitaTraits) {
      const [chapter, verse] = trait.verse.split(".").map(Number);
      expect(
        corpus.some(
          (chunk) =>
            chunk.chapter === chapter &&
            chunk.verse_start <= verse &&
            chunk.verse_end >= verse,
        ),
        `missing corpus verse for ${trait.id}: ${trait.verse}`,
      ).toBe(true);
    }
  });

  it.each([
    ["I feel angry and do not want to react badly.", "anger"],
    ["I am worried about tomorrow.", "worry"],
    ["I keep comparing my career with my friends.", "career_comparison"],
    ["I cannot stop doomscrolling and craving my phone.", "addictive_desire"],
    ["I had an argument with my wife and I feel I am lost", "conflict"],
  ])("matches %s to %s", (message, expected) => {
    expect(classifyOfflineTrait(message)?.id).toBe(expected);
  });

  it("abstains when no trait can be matched confidently", () => {
    expect(classifyOfflineTrait("Please explain a database index.")).toBeNull();
  });

  it("creates a structured, cited offline message", () => {
    const message = createOfflineReflection("I feel angry.", "chosen");

    expect(message?.reflection).toMatchObject({
      id: "anger",
      label: "Anger",
      type: "emotion",
      source: "offline",
      reason: "chosen",
      verse: "2.62",
    });
    expect(message?.citations).toEqual(["Bhagavad Gita 2.62"]);
  });

  it("exposes every trait type as a filter", () => {
    expect(TRAIT_TYPES).toHaveLength(10);
    expect(new Set(TRAIT_TYPES.map(({ id }) => id))).toEqual(
      new Set(gitaTraits.map(({ type }) => type)),
    );
  });

  it("filters the complete library by category and searchable aliases", () => {
    const emotions = searchOfflineTraits("", "emotion");
    expect(emotions).toHaveLength(9);
    expect(emotions.every(({ type }) => type === "emotion")).toBe(true);
    expect(searchOfflineTraits("racing thoughts").map(({ id }) => id)).toContain("restless_mind");
  });

  it("creates guidance directly from a selected trait", () => {
    expect(createOfflineReflectionForTrait("anger")?.reflection).toMatchObject({
      id: "anger",
      label: "Anger",
      reason: "chosen",
      source: "offline",
    });
    expect(createOfflineReflectionForTrait("not-a-trait")).toBeNull();
  });

  it("blocks restricted input and escalates crisis language before matching", () => {
    expect(evaluateOfflineSafety("This is f***ing awful").action).toBe("block");
    expect(evaluateOfflineSafety("I want to hurt myself").action).toBe("escalate");
    expect(evaluateOfflineSafety("I feel angry").action).toBe("allow");
  });
});
