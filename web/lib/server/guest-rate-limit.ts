import { createHmac } from "node:crypto";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

export type GuestRateLimitResult =
  | { allowed: true; remaining?: number; reset?: number }
  | { allowed: false; status: 429 | 503; message: string; remaining?: number; reset?: number };

let limiter: Ratelimit | null = null;

function usableSecret(value: string | undefined): string | null {
  const normalized = value?.trim();
  if (!normalized || /replace[-_ ]?with|your[-_ ]/i.test(normalized)) return null;
  return normalized;
}

function configuredLimiter(): Ratelimit | null {
  if (limiter) return limiter;
  const url = usableSecret(process.env.UPSTASH_REDIS_REST_URL);
  const token = usableSecret(process.env.UPSTASH_REDIS_REST_TOKEN);
  if (!url || !token) return null;
  limiter = new Ratelimit({
    redis: new Redis({ url, token }),
    limiter: Ratelimit.slidingWindow(10, "10 m"),
    prefix: "gita-guide:guest-rate-limit",
    analytics: true,
    timeout: 2_000,
  });
  return limiter;
}

function clientAddress(request: Request): string {
  if (process.env.VERCEL) {
    return request.headers.get("x-vercel-forwarded-for")?.trim()
      || request.headers.get("x-forwarded-for")?.trim()
      || "unknown";
  }
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || request.headers.get("x-real-ip")?.trim() || "unknown";
}

export async function limitGuestRequest(request: Request): Promise<GuestRateLimitResult> {
  const rateLimiter = configuredLimiter();
  const secret = usableSecret(process.env.GUEST_RATE_LIMIT_SECRET);
  if (!rateLimiter || !secret) {
    if (process.env.NODE_ENV !== "production") return { allowed: true };
    return {
      allowed: false,
      status: 503,
      message: "Guest access is temporarily unavailable because abuse protection is not configured.",
    };
  }

  const identifier = createHmac("sha256", secret).update(clientAddress(request)).digest("hex");
  try {
    const result = await rateLimiter.limit(identifier);
    if (result.reason === "timeout") {
      return {
        allowed: false,
        status: 503,
        message: "Guest access is temporarily unavailable. Please try again shortly.",
      };
    }
    if (result.success) return { allowed: true, remaining: result.remaining, reset: result.reset };
    return {
      allowed: false,
      status: 429,
      message: "You have reached the request limit. Please wait a few minutes and try again.",
      remaining: result.remaining,
      reset: result.reset,
    };
  } catch {
    return {
      allowed: false,
      status: 503,
      message: "Guest access is temporarily unavailable. Please try again shortly.",
    };
  }
}
