/**
 * Direct security tests for src/proxy.ts (F-5).
 *
 * The proxy is the security boundary for route protection, session
 * rotation, and invitation token handling. These tests pin its contract,
 * including the F-3 invariant: a successful refresh rotation is ALWAYS
 * persisted to the outgoing browser response.
 */

import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ACCESS_COOKIE,
  INVITE_CONTINUATION_COOKIE,
  REFRESH_COOKIE,
} from "@/lib/auth/cookies";
import { proxy } from "./proxy";

vi.mock("@/lib/auth/invite-continuation", () => ({
  createInviteContinuation: vi.fn(async () => "test-nonce-001"),
  consumeInviteContinuation: vi.fn(async () => null),
  setInviteContinuationStore: vi.fn(),
  RedisInviteContinuationStore: class {},
}));

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function get(path: string, cookieHeader?: string, method = "GET"): NextRequest {
  return new NextRequest(`http://localhost${path}`, {
    method,
    headers: cookieHeader ? { cookie: cookieHeader } : {},
  });
}

interface BackendStubs {
  me?: (auth: string | null) => Response;
  refresh?: (body: unknown) => Response;
}

/** Stub the backend; records every backend URL hit for exactly-once assertions. */
function stubBackend(stubs: BackendStubs): string[] {
  const seen: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      seen.push(String(url));
      if (String(url).endsWith("/auth/me")) {
        return stubs.me
          ? stubs.me(new Headers(init.headers).get("authorization"))
          : jsonResponse(401, { detail: "Unauthorized" });
      }
      if (String(url).endsWith("/auth/refresh")) {
        return stubs.refresh
          ? stubs.refresh(JSON.parse(init.body as string))
          : jsonResponse(401, { detail: "Invalid or revoked refresh token" });
      }
      return jsonResponse(404, { detail: "Not Found" });
    }),
  );
  return seen;
}

const VALID_ME = () =>
  jsonResponse(200, { id: "u1", email: "u@example.com", is_active: true, is_super_admin: false });
const EXPIRED_ME = () => jsonResponse(401, { detail: "Token has expired" });
const FRESH_PAIR = () =>
  jsonResponse(200, {
    access_token: "fresh-at-1",
    refresh_token: "fresh-rt-1",
    token_type: "bearer",
  });
const DEAD_REFRESH = () => jsonResponse(401, { detail: "Invalid or revoked refresh token" });

function isPassThrough(res: Response): boolean {
  return res.headers.get("x-middleware-next") === "1" && !res.headers.get("location");
}

describe("proxy: protected routes", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("redirects to login when there is no session", async () => {
    stubBackend({});
    const res = await proxy(get("/customer/dashboard"));
    expect(res.status).toBe(307);
    const location = res.headers.get("location") ?? "";
    expect(location).toContain("/login");
    expect(location).toContain(encodeURIComponent("/customer/dashboard"));
  });

  it("passes a valid session through untouched", async () => {
    stubBackend({ me: () => VALID_ME() });
    const res = await proxy(get("/salon/dashboard", `${ACCESS_COOKIE}=good-at`));
    expect(isPassThrough(res)).toBe(true);
    expect(res.cookies.get(ACCESS_COOKIE)).toBeUndefined();
  });

  it("rotates exactly once on expired access and persists the fresh pair", async () => {
    const seen = stubBackend({ me: () => EXPIRED_ME(), refresh: () => FRESH_PAIR() });
    const res = await proxy(get("/salon/dashboard", `${ACCESS_COOKIE}=old-at; ${REFRESH_COOKIE}=good-rt`));
    expect(seen.filter((u) => u.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(isPassThrough(res)).toBe(true);
    // F-3 invariant: the rotated pair MUST reach the browser.
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("fresh-at-1");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("fresh-rt-1");
  });

  it("redirects to login and clears cookies when refresh fails", async () => {
    stubBackend({ me: () => EXPIRED_ME(), refresh: () => DEAD_REFRESH() });
    const res = await proxy(get("/customer/dashboard", `${ACCESS_COOKIE}=old-at; ${REFRESH_COOKIE}=dead-rt`));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login");
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("");
  });
});

describe("proxy: auth pages", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("bounces an authenticated user away from /login", async () => {
    stubBackend({ me: () => VALID_ME() });
    const res = await proxy(get("/login", `${ACCESS_COOKIE}=good-at`));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe("http://localhost/customer/dashboard");
  });

  it("preserves a safe ?next= when bouncing", async () => {
    stubBackend({ me: () => VALID_ME() });
    const res = await proxy(get("/login?next=/salon/dashboard", `${ACCESS_COOKIE}=good-at`));
    expect(res.headers.get("location")).toBe("http://localhost/salon/dashboard");
  });

  it("rejects a malicious ?next= and falls back safely", async () => {
    stubBackend({ me: () => VALID_ME() });
    for (const evil of ["//evil.com/phish", "https://evil.com", "/\\evil.com"]) {
      const res = await proxy(
        get(`/login?next=${encodeURIComponent(evil)}`, `${ACCESS_COOKIE}=good-at`),
      );
      expect(res.headers.get("location")).toBe("http://localhost/customer/dashboard");
    }
  });

  it("renders the form (no redirect loop) when the session is stale", async () => {
    stubBackend({ me: () => EXPIRED_ME(), refresh: () => DEAD_REFRESH() });
    const res = await proxy(get("/login", `${ACCESS_COOKIE}=old-at; ${REFRESH_COOKIE}=dead-rt`));
    // A redirect here would bounce /login -> /login forever.
    expect(isPassThrough(res)).toBe(true);
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("");
  });
});

describe("proxy: invitation entry point", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("strips the raw token from the URL immediately for authenticated users", async () => {
    stubBackend({ me: () => VALID_ME() });
    const res = await proxy(get("/invite/accept?token=raw-invite-token-xyz", `${ACCESS_COOKIE}=good-at`));
    expect(res.status).toBe(307);
    const location = res.headers.get("location") ?? "";
    expect(location).toBe("http://localhost/invite/accept");
    expect(location).not.toContain("raw-invite-token-xyz");
  });

  it("parks the token server-side; the nonce cookie contains no raw token", async () => {
    stubBackend({ me: () => VALID_ME() });
    const res = await proxy(get("/invite/accept?token=raw-invite-token-xyz", `${ACCESS_COOKIE}=good-at`));
    const nonceCookie = res.cookies.get(INVITE_CONTINUATION_COOKIE)?.value;
    expect(nonceCookie).toBe("test-nonce-001");
    expect(nonceCookie).not.toContain("raw-invite-token-xyz");
  });

  it("parks the token and continues through login when unauthenticated", async () => {
    stubBackend({});
    const res = await proxy(get("/invite/accept?token=raw-invite-token-xyz"));
    expect(res.status).toBe(307);
    const location = res.headers.get("location") ?? "";
    expect(location).toContain("/login");
    expect(location).toContain(encodeURIComponent("/invite/accept"));
    expect(location).not.toContain("raw-invite-token-xyz");
    expect(res.cookies.get(INVITE_CONTINUATION_COOKIE)?.value).toBe("test-nonce-001");
  });

  it("persists fresh tokens when the invite session was refreshed (F-3 regression)", async () => {
    // The exact defect: handleInvite() used to return a bare
    // NextResponse.next() here, leaving the browser with the rotated-out
    // refresh token. This test fails if that path regresses.
    const seen = stubBackend({ me: () => EXPIRED_ME(), refresh: () => FRESH_PAIR() });
    const res = await proxy(get("/invite/accept", `${ACCESS_COOKIE}=old-at; ${REFRESH_COOKIE}=good-rt`));
    expect(seen.filter((u) => u.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(isPassThrough(res)).toBe(true);
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("fresh-at-1");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("fresh-rt-1");
  });

  it("ignores non-GET requests to /invite/accept", async () => {
    stubBackend({ me: () => VALID_ME() });
    const res = await proxy(get("/invite/accept?token=raw-xyz", `${ACCESS_COOKIE}=good-at`, "POST"));
    expect(isPassThrough(res)).toBe(true);
    expect(res.cookies.get(INVITE_CONTINUATION_COOKIE)).toBeUndefined();
  });
});
