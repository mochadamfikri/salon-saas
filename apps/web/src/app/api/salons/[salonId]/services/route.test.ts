import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth/cookies";
import { GET, POST } from "./route";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const context = { params: Promise.resolve({ salonId: "path-salon" }) };
const req = (url: string, method = "GET", body?: unknown, authenticated = true) => new NextRequest(url, { method, headers: { ...(authenticated ? { cookie: `${ACCESS_COOKIE}=token` } : {}), ...(body === undefined ? {} : { "content-type": "application/json" }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

describe("service catalog BFF", () => {
  beforeEach(() => vi.unstubAllGlobals());
  it("lists through backend with auth cookie but no token in response", async () => {
    const mock = vi.fn(async (url: string, init?: RequestInit) => { expect(url).toContain("/salons/path-salon/services"); expect(init?.method ?? "GET").toBe("GET"); return json(200, []); }); vi.stubGlobal("fetch", mock);
    const response = await GET(req("http://localhost/api"), context);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ ok: true, services: [] });
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(mock.mock.calls[0][1]?.headers).toMatchObject({ authorization: "Bearer token" });
  });
  it("uses URL salon context, ignores body salon identifiers, and forwards string money", async () => {
    const mock = vi.fn(async (_url: string, init: RequestInit) => json(201, { ...JSON.parse(String(init.body)), id: "svc", salon_id: "path-salon", is_active: true })); vi.stubGlobal("fetch", mock);
    const response = await POST(req("http://localhost/api", "POST", { salon_id: "attacker-salon", name: "Cut", duration_minutes: 30, price_amount: "10.25" }), context);
    expect(response.status).toBe(201);
    expect(mock.mock.calls[0][0]).toContain("/salons/path-salon/services");
    expect(JSON.parse(String(mock.mock.calls[0][1]?.body))).not.toHaveProperty("salon_id");
    expect(JSON.parse(String(mock.mock.calls[0][1]?.body)).price_amount).toBe("10.25");
  });
  it("maps backend 403 and 404 safely", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(403, { detail: "forbidden" })));
    expect((await GET(req("http://localhost/api"), context)).status).toBe(403);
    vi.stubGlobal("fetch", vi.fn(async () => json(404, { detail: "Service not found" })));
    expect((await GET(req("http://localhost/api"), context)).status).toBe(404);
  });
  it("requires auth and rejects invalid create payload with 422", async () => {
    const mock = vi.fn(async () => json(201, {})); vi.stubGlobal("fetch", mock);
    expect((await GET(req("http://localhost/api", "GET", undefined, false), context)).status).toBe(401);
    expect((await POST(req("http://localhost/api", "POST", { name: "Cut", duration_minutes: 0, price_amount: "1.00" }), context)).status).toBe(422);
    expect(mock).not.toHaveBeenCalled();
  });
  it("uses Phase 1 refresh flow and persists rotated HttpOnly cookies", async () => {
    let serviceCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/auth/refresh")) return json(200, { access_token: "rotated-access", refresh_token: "rotated-refresh", token_type: "bearer" });
      serviceCalls += 1;
      return serviceCalls === 1 ? json(401, { detail: "Unauthorized" }) : json(200, []);
    }));
    const request = new NextRequest("http://localhost/api", { headers: { cookie: `${ACCESS_COOKIE}=expired; ${REFRESH_COOKIE}=refresh-old` } });
    const response = await GET(request, context);
    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toContain("HttpOnly");
    expect(JSON.stringify(await response.json())).not.toContain("rotated-access");
  });
});
