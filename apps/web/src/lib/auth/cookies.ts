/**
 * HttpOnly session cookie definitions.
 *
 * Security contract (per prompt + Next.js 16 auth guide):
 * - Tokens NEVER live in localStorage / sessionStorage / IndexedDB.
 * - `httpOnly: true` always — browser JS cannot read them.
 * - `secure: true` in every non-development environment.
 * - `sameSite: "lax"` minimum.
 * - Short-lived access cookie (~15 min, matches backend JWT lifetime).
 * - Longer-lived refresh cookie (~30 days, matches backend session lifetime).
 */

export const ACCESS_COOKIE = "salon_at";
export const REFRESH_COOKIE = "salon_rt";

/** Backend JWT access-token lifetime: 15 minutes. */
export const ACCESS_COOKIE_MAX_AGE = 15 * 60;
/** Backend refresh-session lifetime: 30 days. */
export const REFRESH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60;

export interface CookieAttributes {
  httpOnly: boolean;
  secure: boolean;
  sameSite: "lax" | "strict" | "none";
  path: string;
  maxAge: number;
}

export function isProductionEnvironment(nodeEnv: string | undefined): boolean {
  return nodeEnv === "production";
}

export function accessCookieAttributes(nodeEnv: string | undefined): CookieAttributes {
  return {
    httpOnly: true,
    // Secure in every non-development environment (production, staging, test).
    secure: nodeEnv !== "development",
    sameSite: "lax",
    path: "/",
    maxAge: ACCESS_COOKIE_MAX_AGE,
  };
}

export function refreshCookieAttributes(nodeEnv: string | undefined): CookieAttributes {
  return {
    httpOnly: true,
    secure: nodeEnv !== "development",
    sameSite: "lax",
    path: "/",
    maxAge: REFRESH_COOKIE_MAX_AGE,
  };
}

/** Attributes that expire a cookie immediately (logout / session invalidation). */
export function expiredCookieAttributes(nodeEnv: string | undefined = process.env.NODE_ENV): CookieAttributes {
  return {
    httpOnly: true,
    // Must mirror the Secure flag used when the cookie was set, otherwise
    // browsers keep the original cookie (notably non-secure dev cookies).
    secure: nodeEnv !== "development",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  };
}

/**
 * Short-lived nonce cookie that bridges an invitation link across the
 * login/register flow. It holds only a random nonce — the raw invitation
 * token itself is parked server-side (see invite-continuation.ts) and is
 * never written to cookies, URLs, storage, or client props.
 */
export const INVITE_CONTINUATION_COOKIE = "salon_ic";
/** Invitation continuation lifetime: 10 minutes. */
export const INVITE_CONTINUATION_MAX_AGE = 10 * 60;

export function inviteContinuationCookieAttributes(
  nodeEnv: string | undefined = process.env.NODE_ENV,
): CookieAttributes {
  return {
    httpOnly: true,
    secure: nodeEnv !== "development",
    sameSite: "lax",
    path: "/invite",
    maxAge: INVITE_CONTINUATION_MAX_AGE,
  };
}

export interface SessionTokens {
  accessToken: string | undefined;
  refreshToken: string | undefined;
}

/**
 * Decode a cookie value written by this module (encodeURIComponent on write).
 * Falls back to the raw value when decoding fails so a malformed value can
 * never crash request handling — it simply won't authenticate.
 */
export function decodeCookieValue(value: string | undefined): string | undefined {
  if (!value) return undefined;
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** Pure cookie-header parser (used by proxy + tests). */
export function parseSessionTokens(cookieHeader: string | null | undefined): SessionTokens {
  if (!cookieHeader) return { accessToken: undefined, refreshToken: undefined };
  const pairs = cookieHeader.split(";");
  let accessToken: string | undefined;
  let refreshToken: string | undefined;
  for (const pair of pairs) {
    const idx = pair.indexOf("=");
    if (idx < 0) continue;
    const name = pair.slice(0, idx).trim();
    const value = pair.slice(idx + 1).trim();
    if (name === ACCESS_COOKIE && value) accessToken = decodeCookieValue(value);
    if (name === REFRESH_COOKIE && value) refreshToken = decodeCookieValue(value);
  }
  return { accessToken, refreshToken };
}

export function hasAnySessionToken(tokens: SessionTokens): boolean {
  return Boolean(tokens.accessToken ?? tokens.refreshToken);
}

/**
 * Rebuild a Cookie header with the session token pair replaced.
 * Used by the proxy to forward a request with freshly rotated tokens so
 * downstream server components see the new session without an extra redirect.
 */
export function withSessionTokens(cookieHeader: string | null | undefined, tokens: SessionTokens): string {
  const parts = (cookieHeader ?? "")
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .filter(
      (part) => !part.startsWith(`${ACCESS_COOKIE}=`) && !part.startsWith(`${REFRESH_COOKIE}=`),
    );
  if (tokens.accessToken) parts.push(`${ACCESS_COOKIE}=${encodeURIComponent(tokens.accessToken)}`);
  if (tokens.refreshToken) parts.push(`${REFRESH_COOKIE}=${encodeURIComponent(tokens.refreshToken)}`);
  return parts.join("; ");
}
