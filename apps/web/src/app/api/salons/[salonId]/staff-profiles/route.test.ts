import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ACCESS_COOKIE } from "@/lib/auth/cookies";
import { GET, POST } from "./route";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const context = { params: Promise.resolve({ salonId: "path-salon" }) };
const req = (method = "GET", body?: unknown) => new NextRequest("http://localhost/api", { method, headers: { cookie: `${ACCESS_COOKIE}=token`, ...(body === undefined ? {} : { "content-type": "application/json" }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

describe("staff profile BFF", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("lists tenant profiles without exposing access tokens", async () => {
    const mock = vi.fn(async (url: string, init?: RequestInit) => { expect(url).toContain("/salons/path-salon/staff-profiles"); void init; return json(200, []); });
    vi.stubGlobal("fetch", mock);
    const response = await GET(req(), context);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ ok: true, profiles: [] });
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(mock.mock.calls[0]?.[1]?.headers).toMatchObject({ authorization: "Bearer token" });
  });

  it("creates with membership_id and preserves backend conflict semantics", async () => {
    const mock = vi.fn(async (_url: string, init: RequestInit) => {
      expect(JSON.parse(String(init.body))).toEqual({ membership_id: "member-1" });
      return json(409, { detail: "duplicate" });
    });
    vi.stubGlobal("fetch", mock);
    expect((await POST(req("POST", { membership_id: "member-1" }), context)).status).toBe(409);
  });

  it("rejects invalid profile creation before calling the backend", async () => {
    const mock = vi.fn(async () => json(201, {}));
    vi.stubGlobal("fetch", mock);
    expect((await POST(req("POST", { membership_id: 42 }), context)).status).toBe(422);
    expect(mock).not.toHaveBeenCalled();
  });
});
