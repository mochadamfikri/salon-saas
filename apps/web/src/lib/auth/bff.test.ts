import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  applySessionOutcome,
  authorizedCall,
  authorizedCallWithTokens,
  bffErrorResponse,
  clearAuthCookies,
  createBackendClient,
  getRequestTokens,
  setAuthCookies,
} from "./bff";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "./cookies";
import type { BackendTokenPair } from "./contracts";

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const pair = (n: number): BackendTokenPair => ({
  access_token: `access-${n}`,
  refresh_token: `refresh-${n}`,
  token_type: "bearer",
});

function authedRequest(cookieHeader: string): NextRequest {
  return new NextRequest("http://localhost/api/x", { headers: { cookie: cookieHeader } });
}

describe("getRequestTokens", () => {
  it("reads and decodes both session cookies", () => {
    const req = authedRequest(
      `${ACCESS_COOKIE}=${encodeURIComponent("a/b+c")}; ${REFRESH_COOKIE}=rt1`,
    );
    expect(getRequestTokens(req)).toEqual({ accessToken: "a/b+c", refreshToken: "rt1" });
  });

  it("returns undefined tokens when cookies are absent", () => {
    expect(getRequestTokens(authedRequest(""))).toEqual({
      accessToken: undefined,
      refreshToken: undefined,
    });
  });
});

describe("authorizedCallWithTokens", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("succeeds with a valid access token and no refresh", async () => {
    const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
      expect(new Headers(init.headers).get("authorization")).toBe("Bearer at1");
      return jsonResponse(200, { ok: true });
    }) as unknown as typeof fetch;
    const backend = createBackendClient(fetchImpl);
    const outcome = await authorizedCallWithTokens(
      { backend, tokens: { accessToken: "at1", refreshToken: "rt1" } },
      (token) => backend.getMe(token),
    );
    expect(outcome.result.ok).toBe(true);
    expect(outcome.refreshedTokens).toBeUndefined();
    expect(outcome.sessionInvalidated).toBeUndefined();
  });

  it("is unauthorized without any session token and never calls the backend", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {})) as unknown as typeof fetch;
    const backend = createBackendClient(fetchImpl);
    const outcome = await authorizedCallWithTokens(
      { backend, tokens: { accessToken: undefined, refreshToken: undefined } },
      (token) => backend.getMe(token),
    );
    expect(outcome.result.ok).toBe(false);
    if (!outcome.result.ok) expect(outcome.result.code).toBe("unauthorized");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("refreshes exactly once after a 401 and retries the call", async () => {
    let meCalls = 0;
    const fetchImpl = vi.fn(async (url: string) => {
      if (String(url).endsWith("/auth/me")) {
        meCalls += 1;
        return meCalls === 1
          ? jsonResponse(401, { detail: "Token has expired" })
          : jsonResponse(200, { id: "u1" });
      }
      if (String(url).endsWith("/auth/refresh")) return jsonResponse(200, pair(2));
      return jsonResponse(404, {});
    }) as unknown as typeof fetch;
    const backend = createBackendClient(fetchImpl);
    const outcome = await authorizedCallWithTokens(
      { backend, tokens: { accessToken: "stale", refreshToken: "rt1" } },
      (token) => backend.getMe(token),
    );
    expect(outcome.result.ok).toBe(true);
    expect(outcome.refreshedTokens).toEqual(pair(2));
    expect(meCalls).toBe(2);
  });

  it("marks the session invalidated when refresh fails (no retry loop)", async () => {
    let refreshCalls = 0;
    const fetchImpl = vi.fn(async (url: string) => {
      if (String(url).endsWith("/auth/refresh")) {
        refreshCalls += 1;
        return jsonResponse(401, { detail: "Invalid or revoked refresh token" });
      }
      return jsonResponse(401, { detail: "Token has expired" });
    }) as unknown as typeof fetch;
    const backend = createBackendClient(fetchImpl);
    const outcome = await authorizedCallWithTokens(
      { backend, tokens: { accessToken: "stale", refreshToken: "dead" } },
      (token) => backend.getMe(token),
    );
    expect(outcome.result.ok).toBe(false);
    expect(outcome.sessionInvalidated).toBe(true);
    expect(refreshCalls).toBe(1);
  });

  it("does not treat non-401 backend errors as session problems", async () => {
    const fetchImpl = vi.fn(async (url: string) => {
      if (String(url).endsWith("/auth/refresh")) return jsonResponse(200, pair(2));
      return jsonResponse(403, { detail: "Forbidden" });
    }) as unknown as typeof fetch;
    const backend = createBackendClient(fetchImpl);
    const outcome = await authorizedCallWithTokens(
      { backend, tokens: { accessToken: "at1", refreshToken: "rt1" } },
      (token) => backend.getMe(token),
    );
    expect(outcome.result.ok).toBe(false);
    if (!outcome.result.ok) expect(outcome.result.code).toBe("forbidden");
    expect(outcome.refreshedTokens).toBeUndefined();
  });

  it("does not invalidate the session when the refresh is rate limited", async () => {
    const fetchImpl = vi.fn(async (url: string) => {
      if (String(url).endsWith("/auth/refresh")) {
        return new Response(JSON.stringify({ detail: "Too many requests." }), {
          status: 429,
          headers: { "content-type": "application/json", "retry-after": "30" },
        });
      }
      return jsonResponse(401, { detail: "Token has expired" });
    }) as unknown as typeof fetch;
    const backend = createBackendClient(fetchImpl);
    const outcome = await authorizedCallWithTokens(
      { backend, tokens: { accessToken: "stale", refreshToken: "rt1" } },
      (token) => backend.getMe(token),
    );
    expect(outcome.result.ok).toBe(false);
    if (!outcome.result.ok) {
      expect(outcome.result.code).toBe("rate_limited");
      expect(outcome.result.status).toBe(429);
      expect(outcome.result.retryAfterSeconds).toBe(30);
    }
    // A 429 is not a dead session: the caller must NOT clear cookies.
    expect(outcome.sessionInvalidated).toBeUndefined();
    expect(outcome.refreshedTokens).toBeUndefined();
  });
});

describe("authorizedCall (request variant)", () => {
  it("reads tokens from the request cookies", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { id: "u1" })) as unknown as typeof fetch;
    const backend = createBackendClient(fetchImpl);
    const req = authedRequest(`${ACCESS_COOKIE}=at1`);
    const outcome = await authorizedCall({ backend, req }, (token) => backend.getMe(token));
    expect(outcome.result.ok).toBe(true);
  });
});

describe("setAuthCookies / clearAuthCookies", () => {
  it("sets HttpOnly cookies and round-trips encoded values", () => {
    const res = NextResponse.json({ ok: true });
    setAuthCookies(res, { ...pair(1), access_token: "a/b+c" }, "test");
    const access = res.cookies.get(ACCESS_COOKIE);
    const refresh = res.cookies.get(REFRESH_COOKIE);
    expect(access?.httpOnly).toBe(true);
    expect(refresh?.httpOnly).toBe(true);
    expect(access?.sameSite).toBe("lax");
    expect(access?.secure).toBe(true);
    // Encoded on write, decodable on read.
    expect(decodeURIComponent(access?.value ?? "")).toBe("a/b+c");
    expect(refresh?.value).toBe("refresh-1");
  });

  it("does not set Secure in development", () => {
    const res = NextResponse.json({ ok: true });
    setAuthCookies(res, pair(1), "development");
    expect(res.cookies.get(ACCESS_COOKIE)?.secure).toBe(false);
  });

  it("clears both cookies with environment-consistent attributes", () => {
    const res = NextResponse.json({ ok: true });
    clearAuthCookies(res, "development");
    const access = res.cookies.get(ACCESS_COOKIE);
    const refresh = res.cookies.get(REFRESH_COOKIE);
    expect(access?.value).toBe("");
    expect(refresh?.value).toBe("");
    expect(access?.secure).toBe(false);
  });
});

describe("applySessionOutcome", () => {
  it("persists refreshed tokens", () => {
    const res = NextResponse.json({ ok: true });
    applySessionOutcome(res, { refreshedTokens: pair(7) }, "test");
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("access-7");
  });

  it("clears cookies when the session was invalidated", () => {
    const res = NextResponse.json({ ok: false });
    applySessionOutcome(res, { sessionInvalidated: true }, "test");
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("");
  });
});

describe("bffErrorResponse", () => {
  it("maps codes to HTTP statuses and merges extra fields", () => {
    expect(bffErrorResponse("invalid_credentials", "m").status).toBe(401);
    expect(bffErrorResponse("email_taken", "m").status).toBe(400);
    expect(bffErrorResponse("slug_taken", "m").status).toBe(400);
    expect(bffErrorResponse("invitation_expired", "m").status).toBe(410);
    expect(bffErrorResponse("invitation_already_accepted", "m").status).toBe(409);
    expect(bffErrorResponse("invitation_duplicate_membership", "m").status).toBe(409);
    expect(bffErrorResponse("invitation_email_mismatch", "m").status).toBe(422);
    expect(bffErrorResponse("network_error", "m").status).toBe(502);
    expect(bffErrorResponse("unknown_error", "m").status).toBe(500);
    const withState = bffErrorResponse("invitation_expired", "m", { state: "expired" }, 503);
    expect(withState.status).toBe(503);
  });

  it("maps account_inactive to 403 (backend: 403 'Account is not active')", () => {
    const res = bffErrorResponse("account_inactive", "m");
    expect(res.status).toBe(403);
  });

  it("maps generic validation_error to 422 (backend: FastAPI/Pydantic 422)", () => {
    expect(bffErrorResponse("validation_error", "m").status).toBe(422);
  });

  it("carries no token fields in error payloads", async () => {
    const res = bffErrorResponse("invalid_refresh_token", "Your session has expired.");
    const body = (await res.json()) as Record<string, unknown>;
    expect(body).not.toHaveProperty("access_token");
    expect(body).not.toHaveProperty("refresh_token");
    expect(body).not.toHaveProperty("token");
  });
});
