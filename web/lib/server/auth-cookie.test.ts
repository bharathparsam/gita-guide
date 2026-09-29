import { describe, expect, it } from "vitest";
import { hasSupabaseAuthCookie } from "./auth-cookie";

const URL = "https://project-ref.supabase.co";

describe("hasSupabaseAuthCookie", () => {
  it("detects complete and chunked Supabase session cookies", () => {
    expect(hasSupabaseAuthCookie("theme=light; sb-project-ref-auth-token=value", URL)).toBe(true);
    expect(hasSupabaseAuthCookie("sb-project-ref-auth-token.0=part", URL)).toBe(true);
  });

  it("ignores unrelated or forged project cookie names", () => {
    expect(hasSupabaseAuthCookie("theme=light", URL)).toBe(false);
    expect(hasSupabaseAuthCookie("sb-other-auth-token=value", URL)).toBe(false);
    expect(hasSupabaseAuthCookie(null, URL)).toBe(false);
  });
});
