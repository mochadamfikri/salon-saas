/**
 * Next.js 16 `proxy` (replaces the deprecated `middleware` convention).
 *
 * Server-authoritative route protection:
 *  - Protected pages (/customer/*, /salon/*) require a session cookie.
 *    Cookie presence alone only decides the redirect; the backend remains
 *    authoritative — pages/BFF re-validate every request.
 *  - Authenticated users visiting /login or /register are sent to the
 *    customer dashboard (preserving a safe `?next=` continuation).
 *  - When the short-lived access cookie is gone but the refresh cookie
 *    survives, the proxy performs ONE backend refresh and re-issues cookies
 *    before the page renders. A failed refresh clears cookies and redirects
 *    to /login. No infinite loops: a single attempt per request.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { BackendClient } from "@/lib/auth/backend";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  accessCookieAttributes,
  expiredCookieAttributes,
  refreshCookieAttributes,
} from "@/lib/auth/cookies";
import { safeRedirectPath } from "@/lib/auth/validation";

export const config = {
  matcher: ["/customer/:path*", "/salon/:path*", "/login", "/register"],
};

const AUTH_PAGES = new Set(["/login", "/register"]);

function loginRedirect(req: NextRequest): NextResponse {
  const nextParam = req.nextUrl.pathname + req.nextUrl.search;
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(nextParam)}`;
  return NextResponse.redirect(url);
}

function applySessionCookies(
  res: NextResponse,
  accessToken: string,
  refreshToken: string,
): void {
  const nodeEnv = process.env.NODE_ENV;
  res.cookies.set(ACCESS_COOKIE, accessToken, {
    ...accessCookieAttributes(nodeEnv),
  });
  res.cookies.set(REFRESH_COOKIE, refreshToken, {
    ...refreshCookieAttributes(nodeEnv),
  });
}

function clearSessionCookies(res: NextResponse): void {
  const expired = expiredCookieAttributes();
  res.cookies.set(ACCESS_COOKIE, "", { ...expired });
  res.cookies.set(REFRESH_COOKIE, "", { ...expired });
}

export async function proxy(req: NextRequest): Promise<NextResponse> {
  const { pathname } = req.nextUrl;
  const accessToken = req.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = req.cookies.get(REFRESH_COOKIE)?.value;
  const hasSession = Boolean(accessToken ?? refreshToken);

  // Auth pages: bounce already-authenticated users away.
  if (AUTH_PAGES.has(pathname)) {
    if (hasSession) {
      const dest = safeRedirectPath(req.nextUrl.searchParams.get("next"), "/customer/dashboard");
      return NextResponse.redirect(new URL(dest, req.url));
    }
    return NextResponse.next();
  }

  // Protected pages: no session at all -> login.
  if (!accessToken && !refreshToken) {
    return loginRedirect(req);
  }

  // Access cookie present: let the page/BFF validate it against the backend.
  if (accessToken) {
    return NextResponse.next();
  }

  // Access gone but refresh survives: single transparent rotation attempt.
  try {
    const backend = new BackendClient({
      baseUrl: process.env.API_BASE_URL ?? "http://localhost:8000",
      timeoutMs: 8_000,
    });
    const rotated = await backend.refresh({ refresh_token: refreshToken as string });
    if (!rotated.ok) {
      const res = loginRedirect(req);
      clearSessionCookies(res);
      return res;
    }
    const res = NextResponse.next();
    applySessionCookies(res, rotated.data.access_token, rotated.data.refresh_token);
    return res;
  } catch {
    const res = loginRedirect(req);
    clearSessionCookies(res);
    return res;
  }
}
