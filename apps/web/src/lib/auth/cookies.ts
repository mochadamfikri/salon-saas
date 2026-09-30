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
export function expiredCookieAttributes(): CookieAttributes {
  return {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  };
}

export interface SessionTokens {
  accessToken: string | undefined;
  refreshToken: string | undefined;
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
    if (name === ACCESS_COOKIE && value) accessToken = decodeURIComponent(value);
    if (name === REFRESH_COOKIE && value) refreshToken = decodeURIComponent(value);
  }
  return { accessToken, refreshToken };
}

export function hasAnySessionToken(tokens: SessionTokens): boolean {
  return Boolean(tokens.accessToken ?? tokens.refreshToken);
}
