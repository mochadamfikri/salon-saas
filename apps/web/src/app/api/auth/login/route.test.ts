import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth/cookies";
import { POST } from "./route";

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function post(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

const TOKEN_A = "access-token-aaa111";
const TOKEN_R = "refresh-token-bbb222";
const USER = { id: "u1", email: "user@example.com", is_active: true, is_super_admin: false };

function stubBackend(outcomes: { login?: Response; me?: Response }) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).endsWith("/auth/login")) {
        return (
          outcomes.login ??
          jsonResponse(200, { access_token: TOKEN_A, refresh_token: TOKEN_R, token_type: "bearer" })
        );
      }
      if (String(url).endsWith("/auth/me")) {
        return outcomes.me ?? jsonResponse(200, USER);
      }
      return jsonResponse(404, {});
    }),
  );
}

describe("POST /api/auth/login", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("sets HttpOnly cookies on success and never returns tokens in the body", async () => {
    stubBackend({});
    const res = await POST(post({ email: "user@example.com", password: "correct-horse-12" }));
    expect(res.status).toBe(200);

    const access = res.cookies.get(ACCESS_COOKIE);
    const refresh = res.cookies.get(REFRESH_COOKIE);
    expect(access?.value).toBe(TOKEN_A);
    expect(refresh?.value).toBe(TOKEN_R);
    expect(access?.httpOnly).toBe(true);
    expect(refresh?.httpOnly).toBe(true);

    const body = await res.json();
    expect(body).toMatchObject({ ok: true, user: USER });
    const serialized = JSON.stringify(body);
    expect(serialized).not.toContain(TOKEN_A);
    expect(serialized).not.toContain(TOKEN_R);
  });

  it("returns a generic 401 for invalid credentials", async () => {
    stubBackend({ login: jsonResponse(401, { detail: "Invalid email or password" }) });
    const res = await POST(post({ email: "user@example.com", password: "wrong-password" }));
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body).toMatchObject({ ok: false, code: "invalid_credentials" });
    expect(body.message).toBe("Invalid email or password.");
    // No session cookies on failure.
    expect(res.cookies.get(ACCESS_COOKIE)).toBeUndefined();
  });

  it("forwards a backend 403 for inactive accounts (not a 401)", async () => {
    stubBackend({ login: jsonResponse(403, { detail: "Account is not active" }) });
    const res = await POST(post({ email: "user@example.com", password: "x".repeat(12) }));
    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body).toMatchObject({ ok: false, code: "account_inactive" });
    expect(res.cookies.get(ACCESS_COOKIE)).toBeUndefined();
  });

  it("rejects malformed input before touching the backend", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);
    const res = await POST(post({ email: "not-an-email", password: "x".repeat(12) }));
    expect(res.status).toBe(422);
    const body = await res.json();
    expect(body.field).toBe("email");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns 502 when the backend is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );
    const res = await POST(post({ email: "user@example.com", password: "x".repeat(12) }));
    expect(res.status).toBe(502);
  });
});
