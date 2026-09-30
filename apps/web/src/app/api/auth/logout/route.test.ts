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

function post(cookieHeader?: string): NextRequest {
  return new NextRequest("http://localhost/api/auth/logout", {
    method: "POST",
    headers: cookieHeader ? { cookie: cookieHeader } : {},
  });
}

describe("POST /api/auth/logout", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("revokes the backend session and clears both cookies", async () => {
    let revokedWith: string | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        revokedWith = new Headers(init.headers).get("authorization");
        return jsonResponse(200, { message: "Logged out" });
      }),
    );
    const res = await POST(post(`${ACCESS_COOKIE}=access-1`));
    expect(res.status).toBe(200);
    expect(revokedWith).toBe("Bearer access-1");
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("");
  });

  it("refreshes once and revokes when only the refresh token is alive", async () => {
    const seen: string[] = [];
    let logoutAuth: string | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        seen.push(String(url));
        if (String(url).endsWith("/auth/refresh")) {
          return jsonResponse(200, {
            access_token: "fresh-access",
            refresh_token: "fresh-refresh",
            token_type: "bearer",
          });
        }
        logoutAuth = new Headers(init.headers).get("authorization");
        return jsonResponse(200, { message: "Logged out" });
      }),
    );
    const res = await POST(post(`${REFRESH_COOKIE}=refresh-1`));
    expect(res.status).toBe(200);
    expect(seen.filter((u) => u.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(seen.some((u) => u.endsWith("/auth/logout"))).toBe(true);
    expect(logoutAuth).toBe("Bearer fresh-access");
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("");
  });

  it("skips backend revocation when refresh fails but still clears cookies", async () => {
    let logoutCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).endsWith("/auth/refresh")) {
          return jsonResponse(401, { detail: "Invalid or revoked refresh token" });
        }
        logoutCalls += 1;
        return jsonResponse(200, {});
      }),
    );
    const res = await POST(post(`${REFRESH_COOKIE}=dead-refresh`));
    expect(res.status).toBe(200);
    expect(logoutCalls).toBe(0);
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("");
  });

  it("clears cookies even when the backend is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("backend down");
      }),
    );
    const res = await POST(post(`${ACCESS_COOKIE}=access-1`));
    expect(res.status).toBe(200);
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("");
  });
});
