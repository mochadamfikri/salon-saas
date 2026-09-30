/**
 * BFF helpers for Next.js Route Handlers.
 *
 * Centralizes all cookie + backend interaction so Route Handlers stay thin:
 *  - read session cookies from the incoming request
 *  - call the backend with the Bearer access token
 *  - transparent single-attempt refresh on 401 (no infinite loops)
 *  - set / clear HttpOnly cookies on the outgoing response
 *
 * Tokens never leave the server: handlers return only safe payloads
 * (user profile, salon data) — never token pairs.
 */

import { NextRequest, NextResponse } from "next/server";

import {
  BackendClient,
  type BackendErrorCode,
  type BackendResult,
} from "./backend";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  accessCookieAttributes,
  expiredCookieAttributes,
  refreshCookieAttributes,
  type CookieAttributes,
  type SessionTokens,
} from "./cookies";
import type { BackendTokenPair } from "./contracts";

export function backendBaseUrl(): string {
  return process.env.API_BASE_URL ?? "http://localhost:8000";
}

export function createBackendClient(fetchImpl?: typeof fetch): BackendClient {
  return new BackendClient({ baseUrl: backendBaseUrl(), fetchImpl });
}

/** Read raw session tokens from the incoming request's cookies. */
export function getRequestTokens(req: NextRequest): SessionTokens {
  return {
    accessToken: req.cookies.get(ACCESS_COOKIE)?.value || undefined,
    refreshToken: req.cookies.get(REFRESH_COOKIE)?.value || undefined,
  };
}

function applyCookie(
  res: NextResponse,
  name: string,
  value: string,
  attrs: CookieAttributes,
): void {
  res.cookies.set(name, value, {
    httpOnly: attrs.httpOnly,
    secure: attrs.secure,
    sameSite: attrs.sameSite,
    path: attrs.path,
    maxAge: attrs.maxAge,
  });
}

/** Persist a fresh token pair as HttpOnly cookies on the response. */
export function setAuthCookies(
  res: NextResponse,
  tokens: BackendTokenPair,
  nodeEnv: string | undefined = process.env.NODE_ENV,
): void {
  applyCookie(res, ACCESS_COOKIE, tokens.access_token, accessCookieAttributes(nodeEnv));
  applyCookie(res, REFRESH_COOKIE, tokens.refresh_token, refreshCookieAttributes(nodeEnv));
}

/** Expire both session cookies on the response (logout / invalidation). */
export function clearAuthCookies(res: NextResponse): void {
  const expired = expiredCookieAttributes();
  applyCookie(res, ACCESS_COOKIE, "", expired);
  applyCookie(res, REFRESH_COOKIE, "", expired);
}

export interface AuthorizedCallOptions {
  backend: BackendClient;
  req: NextRequest;
}

export interface AuthorizedCallOutcome<T> {
  result: BackendResult<T>;
  /** Set when a refresh rotation succeeded — caller must persist via setAuthCookies. */
  refreshedTokens?: BackendTokenPair;
  /** Set when refresh failed — caller must expire cookies via clearAuthCookies. */
  sessionInvalidated?: boolean;
}

/**
 * Run a backend call with the request's access token, performing at most ONE
 * refresh attempt when the access token is missing or rejected (401).
 *
 * Never throws for auth problems. The caller applies `refreshedTokens` /
 * `sessionInvalidated` to its own response via setAuthCookies/clearAuthCookies.
 */
export async function authorizedCall<T>(
  options: AuthorizedCallOptions,
  call: (accessToken: string) => Promise<BackendResult<T>>,
): Promise<AuthorizedCallOutcome<T>> {
  const { backend, req } = options;
  const tokens = getRequestTokens(req);

  if (tokens.accessToken) {
    const first = await call(tokens.accessToken);
    if (first.ok || first.status !== 401) return { result: first };
    // 401 with an access token: fall through to a single refresh attempt.
  }

  if (!tokens.refreshToken) {
    return {
      result: { ok: false, code: "unauthorized", status: 401, detail: "No session" },
    };
  }

  const rotated = await backend.refresh({ refresh_token: tokens.refreshToken });
  if (!rotated.ok) {
    const code: BackendErrorCode =
      rotated.code === "network_error" ? "network_error" : "invalid_refresh_token";
    return {
      result: { ok: false, code, status: 401, detail: "Session refresh failed" },
      sessionInvalidated: true,
    };
  }

  return {
    result: await call(rotated.data.access_token),
    refreshedTokens: rotated.data,
  };
}

/**
 * Apply a refresh-rotation outcome to the response being returned.
 */
export function applySessionOutcome(
  res: NextResponse,
  outcome: Pick<AuthorizedCallOutcome<unknown>, "refreshedTokens" | "sessionInvalidated">,
  nodeEnv: string | undefined = process.env.NODE_ENV,
): void {
  if (outcome.refreshedTokens) setAuthCookies(res, outcome.refreshedTokens, nodeEnv);
  else if (outcome.sessionInvalidated) clearAuthCookies(res);
}

/**
 * Build a JSON error response for a failed backend call.
 * Maps backend codes to HTTP statuses; never leaks backend internals.
 * `extra` merges additional safe fields (e.g. UI state) into the payload.
 * `statusOverride` replaces the mapped status when needed.
 */
export function bffErrorResponse(
  code: BackendErrorCode,
  message: string,
  extra?: Record<string, unknown>,
  statusOverride?: number,
): NextResponse {
  const status =
    statusOverride ??
    (code === "unauthorized" || code === "invalid_refresh_token"
      ? 401
      : code === "forbidden"
        ? 403
        : code === "not_found" ||
            code === "salon_not_found" ||
            code === "invitation_invalid"
          ? 404
          : code === "invitation_expired" || code === "invitation_revoked"
            ? 410
            : code === "invitation_already_accepted"
              ? 409
              : code === "email_taken" || code === "slug_taken" || code === "validation_error"
                ? 400
                : code === "invitation_email_mismatch"
                  ? 422
                  : code === "rate_limited"
                    ? 429
                    : code === "network_error"
                      ? 502
                      : 500);
  return NextResponse.json({ ok: false, code, message, ...extra }, { status });
}
