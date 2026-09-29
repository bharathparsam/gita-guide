import { describe, expect, it } from "vitest";
import { authErrorMessage, safeAuthNext, validatePassword } from "./auth";

describe("authentication helpers", () => {
  it("requires an eight-character password", () => {
    expect(validatePassword("short")).toBe("Use at least 8 characters.");
    expect(validatePassword("long-enough")).toBeNull();
  });

  it("does not expose provider account lookup details during sign-in", () => {
    expect(authErrorMessage("sign-in", "Invalid login credentials")).toBe(
      "The email or password is incorrect, or the account is not ready yet.",
    );
    expect(authErrorMessage("sign-in", "User not found")).toBe(
      "The email or password is incorrect, or the account is not ready yet.",
    );
  });

  it("provides a recovery path for rate limiting", () => {
    expect(authErrorMessage("recover", "Email rate limit exceeded")).toBe(
      "Too many authentication attempts. Please wait a few minutes and try again.",
    );
  });

  it("allows only same-origin callback destinations", () => {
    expect(safeAuthNext("/reset-password")).toBe("/reset-password");
    expect(safeAuthNext("https://example.com")).toBe("/");
    expect(safeAuthNext("//example.com")).toBe("/");
    expect(safeAuthNext(null)).toBe("/");
  });
});
