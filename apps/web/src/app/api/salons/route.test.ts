import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ACCESS_COOKIE } from "@/lib/auth/cookies";
import { GET, POST } from "./route";

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function authedPost(body: unknown, cookieHeader?: string): NextRequest {
  return new NextRequest("http://localhost/api/salons", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    body: JSON.stringify(body),
  });
}

function authedGet(cookieHeader?: string): NextRequest {
  return new NextRequest("http://localhost/api/salons", {
    headers: cookieHeader ? { cookie: cookieHeader } : {},
  });
}

const AUTH = `${ACCESS_COOKIE}=access-1`;

describe("POST /api/salons", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a salon and returns the backend payload", async () => {
    const salon = { id: "s1", name: "Glow", slug: "glow", status: "onboarding" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        expect(String(url).endsWith("/salons")).toBe(true);
        expect(JSON.parse(init.body as string)).toEqual({ name: "Glow", slug: "glow" });
        return jsonResponse(201, salon);
      }),
    );
    const res = await POST(authedPost({ name: "Glow", slug: "glow" }, AUTH));
    expect(res.status).toBe(201);
    expect(await res.json()).toMatchObject({ ok: true, salon });
  });

  it("forwards { name } without a slug when the slug is omitted", async () => {
    const salon = { id: "s1", name: "Glow", slug: "glow-auto", status: "onboarding" };
    let forwarded: unknown;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        forwarded = JSON.parse(init.body as string);
        return jsonResponse(201, salon);
      }),
    );
    const res = await POST(authedPost({ name: "Glow" }, AUTH));
    expect(res.status).toBe(201);
    expect(forwarded).toEqual({ name: "Glow" });
    expect(forwarded).not.toHaveProperty("slug");
  });

  it("forwards { name } without a slug when the slug is blank", async () => {
    let forwarded: unknown;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        forwarded = JSON.parse(init.body as string);
        return jsonResponse(201, { id: "s1", name: "Glow", slug: "glow-auto", status: "onboarding" });
      }),
    );
    const res = await POST(authedPost({ name: "Glow", slug: "   " }, AUTH));
    expect(res.status).toBe(201);
    expect(forwarded).toEqual({ name: "Glow" });
  });

  it("forwards an explicit valid slug", async () => {
    let forwarded: unknown;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        forwarded = JSON.parse(init.body as string);
        return jsonResponse(201, { id: "s1", name: "Glow", slug: "glow", status: "onboarding" });
      }),
    );
    const res = await POST(authedPost({ name: "Glow", slug: "glow" }, AUTH));
    expect(res.status).toBe(201);
    expect(forwarded).toEqual({ name: "Glow", slug: "glow" });
  });

  it("rejects invalid slugs client-side without hitting the backend", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(201, {}));
    vi.stubGlobal("fetch", fetchMock);
    const res = await POST(authedPost({ name: "Glow", slug: "BAD SLUG" }, AUTH));
    expect(res.status).toBe(400);
    expect((await res.json()).field).toBe("slug");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps a taken slug to a friendly 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(400, { detail: "Salon slug already exists" })),
    );
    const res = await POST(authedPost({ name: "Glow", slug: "glow" }, AUTH));
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.code).toBe("slug_taken");
    expect(body.message).toContain("already taken");
  });

  it("requires authentication", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(201, {}));
    vi.stubGlobal("fetch", fetchMock);
    const res = await POST(authedPost({ name: "Glow", slug: "glow" }));
    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("GET /api/salons", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns memberships from the backend", async () => {
    const salons = [
      {
        id: "m1",
        role: "owner",
        status: "active",
        salon: { id: "s1", name: "Glow", slug: "glow", status: "active" },
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        expect(String(url).endsWith("/me/salons")).toBe(true);
        return jsonResponse(200, salons);
      }),
    );
    const res = await GET(authedGet(AUTH));
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ ok: true, salons });
  });

  it("requires authentication", async () => {
    const res = await GET(authedGet());
    expect(res.status).toBe(401);
  });
});
