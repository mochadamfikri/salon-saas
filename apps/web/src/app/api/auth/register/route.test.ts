import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ACCESS_COOKIE } from "@/lib/auth/cookies";
import { POST } from "./route";

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function post(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/auth/register", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

const USER = { id: "u1", email: "new@example.com", is_active: true, is_super_admin: false };

describe("POST /api/auth/register", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates the account, sets HttpOnly cookies, and returns the user", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).endsWith("/auth/register")) {
          return jsonResponse(200, {
            access_token: "access-123",
            refresh_token: "refresh-456",
            token_type: "bearer",
          });
        }
        return jsonResponse(200, USER);
      }),
    );
    const res = await POST(post({ email: "new@example.com", password: "a-very-long-password" }));
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body).toMatchObject({ ok: true, user: USER });
    expect(res.cookies.get(ACCESS_COOKIE)?.httpOnly).toBe(true);
    expect(JSON.stringify(body)).not.toContain("access-123");
  });

  it("maps duplicate email to a 400 without enumerating accounts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(400, { detail: "Email already registered" })),
    );
    const res = await POST(post({ email: "taken@example.com", password: "a-very-long-password" }));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body).toMatchObject({ ok: false, code: "email_taken" });
    expect(body.message).toContain("already registered");
    expect(res.cookies.get(ACCESS_COOKIE)).toBeUndefined();
  });

  it("enforces the password policy before calling the backend", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);
    const res = await POST(post({ email: "new@example.com", password: "too-short" }));
    expect(res.status).toBe(422);
    expect((await res.json()).field).toBe("password");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
