/**
 * Next.js 16 `proxy` (replaces the deprecated `middleware` convention).
 *
 * Server-authoritative route protection:
 *  - Protected pages (/customer/*, /salon/*) require a *valid* backend
 *    session. Cookie presence alone is never trusted: the access token is
 *    verified against the backend on each navigation, with exactly ONE
 *    refresh attempt when it is missing/expired. A failed refresh clears
 *    the cookies and redirects to /login — no infinite loops, because auth
 *    pages render the form (instead of bouncing) when the session is stale.
 *  - Auth pages (/login, /register) bounce already-authenticated users to
 *    the dashboard (preserving a safe `?next=` continuation); stale
 *    sessions see the form with dead cookies cleared.
 *  - Invitation links (/invite/accept?token=…): the raw token is parked
 *    server-side under a random nonce (HttpOnly `salon_ic` cookie) and
 *    stripped from the URL immediately. The token never enters auth URLs,
 *    cookies, storage, or client props — the page consumes the nonce and
 *    accepts the invitation server-side.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { clearAuthCookies, createBackendClient, setAuthCookies } from "@/lib/auth/bff";
import type { BackendTokenPair } from "@/lib/auth/contracts";
import {
  INVITE_CONTINUATION_COOKIE,
  inviteContinuationCookieAttributes,
  parseSessionTokens,
  hasAnySessionToken,
  withSessionTokens,
} from "@/lib/auth/cookies";
import { createInviteContinuation } from "@/lib/auth/invite-continuation";
import { safeRedirectPath } from "@/lib/auth/validation";

export const config = {
  matcher: ["/customer/:path*", "/salon/:path*", "/login", "/register", "/invite/accept"],
};

const AUTH_PAGES = new Set(["/login", "/register"]);

type SessionResolution =
  | { kind: "none" }
  | { kind: "valid" }
  | { kind: "refreshed"; tokens: BackendTokenPair }
  | { kind: "invalid" };

/**
 * Resolve the request's session against the backend. Verifies the access
 * token and performs at most ONE refresh rotation — never a retry loop.
 * Fail-closed: any backend/network problem resolves to "invalid".
 */
async function resolveSession(req: NextRequest): Promise<SessionResolution> {
  const tokens = parseSessionTokens(req.headers.get("cookie"));
  if (!hasAnySessionToken(tokens)) return { kind: "none" };

  const backend = createBackendClient();
  if (tokens.accessToken) {
    const me = await backend.getMe(tokens.accessToken);
    if (me.ok) return { kind: "valid" };
  }
  if (tokens.refreshToken) {
    const rotated = await backend.refresh({ refresh_token: tokens.refreshToken });
    if (rotated.ok) return { kind: "refreshed", tokens: rotated.data };
  }
  return { kind: "invalid" };
}

function loginRedirect(req: NextRequest, nextPath?: string): NextResponse {
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(nextPath ?? req.nextUrl.pathname + req.nextUrl.search)}`;
  return NextResponse.redirect(url);
}

/**
 * Forward the request with a freshly rotated token pair so the downstream
 * page renders against the new session without another redirect, and
 * persist the pair on the outgoing response.
 *
 * INVARIANT (F-3): a successful refresh rotation is ALWAYS persisted to the
 * browser response. There is no code path that rotates without persisting.
 */
function nextWithFreshSession(
  req: NextRequest,
  tokens: BackendTokenPair,
  nodeEnv: string | undefined,
): NextResponse {
  const headers = new Headers(req.headers);
  headers.set(
    "cookie",
    withSessionTokens(req.headers.get("cookie"), {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    }),
  );
  const res = NextResponse.next({ request: { headers } });
  setAuthCookies(res, tokens, nodeEnv);
  return res;
}

/**
 * Invitation entry point. Parks `?token=` server-side and strips it from
 * the URL; unauthenticated visitors continue through /login with the
 * invitation held server-side (never in the auth URL).
 */
async function handleInvite(req: NextRequest, nodeEnv: string | undefined): Promise<NextResponse> {
  const rawToken = req.nextUrl.searchParams.get("token");
  const session = await resolveSession(req);

  const parkToken = async (res: NextResponse): Promise<NextResponse> => {
    if (rawToken) {
      try {
        const nonce = await createInviteContinuation(rawToken);
        res.cookies.set(INVITE_CONTINUATION_COOKIE, nonce, {
          ...inviteContinuationCookieAttributes(nodeEnv),
        });
      } catch {
        // Store unavailable: continue without a continuation nonce. The
        // visitor can re-open the invite link after login (the page then
        // renders the graceful missing_token state). Never log the token.
      }
    }
    return res;
  };

  if (session.kind === "valid" || session.kind === "refreshed") {
    if (!rawToken) {
      // F-3: a refreshed session MUST have its fresh pair persisted —
      // returning NextResponse.next() bare would leave the browser holding
      // the rotated-out refresh token. The forwarded request also carries
      // the fresh cookies so the page never needs its own (unpersistable)
      // refresh.
      if (session.kind === "refreshed") {
        return nextWithFreshSession(req, session.tokens, nodeEnv);
      }
      return NextResponse.next();
    }
    // Authenticated: strip the token from the URL at once; the page
    // consumes the parked nonce server-side.
    const res = NextResponse.redirect(new URL("/invite/accept", req.url));
    if (session.kind === "refreshed") setAuthCookies(res, session.tokens, nodeEnv);
    return parkToken(res);
  }

  // No usable session: park the token, then continue through login.
  const res = loginRedirect(req, "/invite/accept");
  clearAuthCookies(res, nodeEnv);
  return parkToken(res);
}

export async function proxy(req: NextRequest): Promise<NextResponse> {
  const nodeEnv = process.env.NODE_ENV;
  const { pathname } = req.nextUrl;

  if (pathname === "/invite/accept") {
    if (req.method !== "GET") return NextResponse.next();
    return handleInvite(req, nodeEnv);
  }

  const session = await resolveSession(req);

  // Auth pages: bounce authenticated users away, show the form otherwise.
  if (AUTH_PAGES.has(pathname)) {
    if (session.kind === "valid" || session.kind === "refreshed") {
      const dest = safeRedirectPath(req.nextUrl.searchParams.get("next"), "/customer/dashboard");
      const res = NextResponse.redirect(new URL(dest, req.url));
      if (session.kind === "refreshed") setAuthCookies(res, session.tokens, nodeEnv);
      return res;
    }
    const res = NextResponse.next();
    if (session.kind === "invalid") clearAuthCookies(res, nodeEnv);
    return res;
  }

  // Protected pages.
  if (session.kind === "valid") return NextResponse.next();
  if (session.kind === "refreshed") {
    // Forward with fresh tokens so the page renders without another redirect.
    return nextWithFreshSession(req, session.tokens, nodeEnv);
  }
  const res = loginRedirect(req);
  clearAuthCookies(res, nodeEnv);
  return res;
}
