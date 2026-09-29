export type AuthMode = "sign-in" | "sign-up" | "recover";

const MIN_PASSWORD_LENGTH = 8;

export function safeAuthNext(value: string | null): string {
  if (!value?.startsWith("/") || value.startsWith("//")) return "/";
  return value;
}

export function validatePassword(password: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  return null;
}

export function authErrorMessage(
  mode: AuthMode | "reset",
  providerMessage?: string,
): string {
  const normalized = providerMessage?.toLocaleLowerCase("en") || "";

  if (normalized.includes("rate limit") || normalized.includes("too many")) {
    return "Too many authentication attempts. Please wait a few minutes and try again.";
  }
  if (mode === "sign-in") {
    return "The email or password is incorrect, or the account is not ready yet.";
  }
  if ((mode === "sign-up" || mode === "reset") && normalized.includes("password")) {
    return providerMessage || "That password does not meet the account requirements.";
  }
  if (mode === "recover") {
    return "We could not start password recovery. Please wait a moment and try again.";
  }
  if (mode === "sign-up") {
    return "We could not create the account. Please review the details or try signing in.";
  }
  return "We could not update the password. Please request a new recovery link and try again.";
}
