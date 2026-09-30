import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth/cookies";
import { GET } from "./route";

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function get(cookieHeader?: string): NextRequest {
  return new NextRequest("http://localhost/api/auth/me", {
    headers: cookieHeader ? { cookie: cookieHeader } : {},
  });
}

const USER = { id: "u1", email: "user@example.com", is_active: true, is_super_admin: false };

describe("GET /api/auth/me", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the user when the access token is valid", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        expect(String(url).endsWith("/auth/me")).toBe(true);
        return jsonResponse(200, USER);
      }),
    );
    const res = await GET(get(`${ACCESS_COOKIE}=access-1`));
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ ok: true, user: USER });
  });

  it("returns 401 when there is no session", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);
    const res = await GET(get());
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refreshes once after an expired access token and returns refreshed cookies", async () => {
    let meCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).endsWith("/auth/me")) {
          meCalls += 1;
          return meCalls === 1
            ? jsonResponse(401, { detail: "Token has expired" })
            : jsonResponse(200, USER);
        }
        if (String(url).endsWith("/auth/refresh")) {
          return jsonResponse(200, {
            access_token: "fresh-access",
            refresh_token: "fresh-refresh",
            token_type: "bearer",
          });
        }
        return jsonResponse(404, {});
      }),
    );
    const res = await GET(get(`${ACCESS_COOKIE}=stale-access; ${REFRESH_COOKIE}=refresh-1`));
    expect(res.status).toBe(200);
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("fresh-access");
    expect(meCalls).toBe(2);
  });

  it("clears cookies and returns 401 when refresh fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).endsWith("/auth/refresh")) {
          return jsonResponse(401, { detail: "Invalid or revoked refresh token" });
        }
        return jsonResponse(401, { detail: "Token has expired" });
      }),
    );
    const res = await GET(get(`${ACCESS_COOKIE}=stale-access; ${REFRESH_COOKIE}=dead-refresh`));
    expect(res.status).toBe(401);
    expect(res.cookies.get(ACCESS_COOKIE)?.value).toBe("");
    expect(res.cookies.get(REFRESH_COOKIE)?.value).toBe("");
  });
});
