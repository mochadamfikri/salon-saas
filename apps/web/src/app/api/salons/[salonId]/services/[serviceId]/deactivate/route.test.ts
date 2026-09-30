import { NextRequest } from "next/server";
import { expect, it, vi } from "vitest";
import { ACCESS_COOKIE } from "@/lib/auth/cookies";
import { POST } from "./route";

it("deactivates through the authenticated BFF route", async () => {
  const fetchMock = vi.fn(async (url: string) => {
    expect(url).toContain("/salons/salon1/services/svc1/deactivate");
    return new Response(JSON.stringify({ id: "svc1", is_active: false }), { status: 200, headers: { "content-type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  const req = new NextRequest("http://localhost/api", { method: "POST", headers: { cookie: `${ACCESS_COOKIE}=opaque` } });
  const response = await POST(req, { params: Promise.resolve({ salonId: "salon1", serviceId: "svc1" }) });
  expect(response.status).toBe(200);
  expect((await response.json()).service.is_active).toBe(false);
});
