import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ACCESS_COOKIE } from "@/lib/auth/cookies";
import { PATCH } from "./route";

const body = { id: "svc", salon_id: "salon1", name: "Cut", description: null, category: null, duration_minutes: 30, price_amount: "10.00", currency: "IDR", is_active: true };
const context = { params: Promise.resolve({ salonId: "salon1", serviceId: "svc" }) };
function patch(payload: unknown) { return new NextRequest("http://localhost/api", { method: "PATCH", headers: { cookie: `${ACCESS_COOKIE}=secret-token`, "content-type": "application/json" }, body: JSON.stringify(payload) }); }
const response = (status: number, value: unknown) => new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json" } });

describe("PATCH service BFF", () => {
  beforeEach(() => vi.unstubAllGlobals());
  it("forwards explicit null to clear nullable fields and never returns token material", async () => {
    const fetchMock = vi.fn(async (_url: string, init: RequestInit) => response(200, { ...body, ...JSON.parse(String(init.body)) }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await PATCH(patch({ description: null, category: null }), context);
    expect(result.status).toBe(200);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ description: null, category: null });
    expect(JSON.stringify(await result.json())).not.toContain("secret-token");
  });
  it("does not turn omitted nullable fields into null", async () => {
    const fetchMock = vi.fn(async (_url: string, init: RequestInit) => response(200, { ...body, ...JSON.parse(String(init.body)) }));
    vi.stubGlobal("fetch", fetchMock);
    await PATCH(patch({ name: "New name" }), context);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ name: "New name" });
  });
  it("returns validation feedback for empty patches and required-field nulls", async () => {
    const fetchMock = vi.fn(async () => response(200, body)); vi.stubGlobal("fetch", fetchMock);
    expect((await PATCH(patch({}), context)).status).toBe(422);
    expect((await PATCH(patch({ name: null }), context)).status).toBe(422);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
