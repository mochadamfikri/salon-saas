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

function accept(body: unknown, cookieHeader?: string): NextRequest {
  return new NextRequest("http://localhost/api/invitations/accept", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    body: JSON.stringify(body),
  });
}

const AUTH = `${ACCESS_COOKIE}=access-1`;

describe("POST /api/invitations/accept", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("accepts an invitation and returns membership context", async () => {
    const payload = {
      membership: { id: "m1", role: "staff", status: "active" },
      salon: { id: "s1", name: "Glow", slug: "glow" },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        if (String(url).endsWith("/auth/me")) return jsonResponse(200, { id: "u1" });
        expect(String(url).endsWith("/invitations/accept")).toBe(true);
        expect(JSON.parse(init.body as string)).toEqual({ token: "raw-token" });
        return jsonResponse(200, payload);
      }),
    );
    const res = await POST(accept({ token: "raw-token" }, AUTH));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({ ok: true, state: "success", ...payload });
    expect(JSON.stringify(body)).not.toContain("raw-token");
  });

  it("maps backend invitation states to UI states", async () => {
    const cases: Array<[number, string, number, string]> = [
      [404, "Invitation not found", 404, "invalid"],
      [410, "Invitation expired", 410, "expired"],
      [410, "Invitation revoked", 410, "revoked"],
      [409, "Invitation has already been accepted", 409, "already_accepted"],
      [409, "User already has an active membership in this salon", 409, "already_member"],
      [422, "Invitation email mismatch", 422, "email_mismatch"],
    ];
    for (const [backendStatus, detail, expectedStatus, expectedState] of cases) {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string) => {
          if (String(url).endsWith("/auth/me")) return jsonResponse(200, { id: "u1" });
          return jsonResponse(backendStatus, { detail });
        }),
      );
      const res = await POST(accept({ token: "tok" }, AUTH));
      expect(res.status).toBe(expectedStatus);
      expect((await res.json()).state).toBe(expectedState);
    }
  });

  it("reports invitation_unavailable when the backend route is missing (FastAPI default 404)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).endsWith("/auth/me")) return jsonResponse(200, { id: "u1" });
        return jsonResponse(404, { detail: "Not Found" });
      }),
    );
    const res = await POST(accept({ token: "tok" }, AUTH));
    expect(res.status).toBe(503);
    const body = await res.json();
    expect(body).toMatchObject({ ok: false, state: "error", code: "invitation_unavailable" });
  });

  it("requires a session first", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);
    const res = await POST(accept({ token: "tok" }));
    expect(res.status).toBe(401);
    expect((await res.json()).state).toBe("login_required");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("requires the token in the request body", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);
    const res = await POST(accept({}, AUTH));
    expect(res.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
