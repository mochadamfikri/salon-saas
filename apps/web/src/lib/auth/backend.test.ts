import { describe, expect, it, vi } from "vitest";

import { BackendClient, mapBackendError } from "./backend";

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function mockFetch(handler: (url: string, init: RequestInit) => Response) {
  return vi.fn(async (url: string, init: RequestInit) => handler(url, init)) as unknown as typeof fetch;
}

const TOKENS = { access_token: "at", refresh_token: "rt", token_type: "bearer" };

describe("mapBackendError", () => {
  it("maps auth failures without user enumeration", () => {
    expect(mapBackendError(401, "Invalid email or password")).toBe("invalid_credentials");
    expect(mapBackendError(401, "Invalid or revoked refresh token")).toBe("invalid_refresh_token");
    expect(mapBackendError(401, "Token has expired")).toBe("unauthorized");
  });

  it("maps registration and tenant conflicts", () => {
    expect(mapBackendError(400, "Email already registered")).toBe("email_taken");
    expect(mapBackendError(400, "Salon slug already exists")).toBe("slug_taken");
    expect(mapBackendError(403, "Account is not active")).toBe("account_inactive");
  });

  it("maps invitation states", () => {
    expect(mapBackendError(404, "Invitation not found")).toBe("invitation_invalid");
    expect(mapBackendError(410, "Invitation expired")).toBe("invitation_expired");
    expect(mapBackendError(410, "Invitation revoked")).toBe("invitation_revoked");
    expect(mapBackendError(409, "Invitation has already been accepted")).toBe("invitation_already_accepted");
    expect(
      mapBackendError(409, "User already has an active membership in this salon"),
    ).toBe("invitation_duplicate_membership");
    expect(mapBackendError(422, "Invitation email mismatch")).toBe("invitation_email_mismatch");
  });

  it("keeps already-accepted distinct from duplicate membership on 409", () => {
    // Both are 409 but need different UX; never collapse to unknown_error.
    expect(mapBackendError(409, "Invitation has already been accepted")).toBe(
      "invitation_already_accepted",
    );
    expect(mapBackendError(409, "User already has an active membership in this salon")).toBe(
      "invitation_duplicate_membership",
    );
  });
});

describe("BackendClient", () => {
  it("logs in and returns the token pair", async () => {
    const fetchImpl = mockFetch((url) => {
      expect(url).toBe("https://api.test/auth/login");
      return jsonResponse(200, TOKENS);
    });
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    const result = await client.login({ email: "a@b.com", password: "x".repeat(12) });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.access_token).toBe("at");
  });

  it("sends the Bearer header for authenticated calls", async () => {
    let authHeader: string | null = null;
    const fetchImpl = mockFetch((_url, init) => {
      authHeader = new Headers(init.headers).get("authorization");
      return jsonResponse(200, { id: "1", email: "a@b.com", is_active: true, is_super_admin: false });
    });
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    await client.getMe("secret-access");
    expect(authHeader).toBe("Bearer secret-access");
  });

  it("maps a 401 login to invalid_credentials", async () => {
    const fetchImpl = mockFetch(() => jsonResponse(401, { detail: "Invalid email or password" }));
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    const result = await client.login({ email: "a@b.com", password: "wrong" });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("invalid_credentials");
      expect(result.status).toBe(401);
    }
  });

  it("maps a 400 register to email_taken", async () => {
    const fetchImpl = mockFetch(() => jsonResponse(400, { detail: "Email already registered" }));
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    const result = await client.register({ email: "a@b.com", password: "x".repeat(12) });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("email_taken");
  });

  it("returns network_error when fetch throws", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("down");
    }) as unknown as typeof fetch;
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    const result = await client.getMe("x");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("network_error");
  });

  it("maps missing invitation endpoint to invitation_unavailable", async () => {
    // FastAPI default 404 body when the route does not exist (Checkpoint D pending).
    const fetchImpl = mockFetch(() => jsonResponse(404, { detail: "Not Found" }));
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    const result = await client.acceptInvitation("at", { token: "raw" });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("invitation_unavailable");
  });

  it("maps a real invalid invitation token distinctly", async () => {
    const fetchImpl = mockFetch(() => jsonResponse(404, { detail: "Invitation not found" }));
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    const result = await client.acceptInvitation("at", { token: "raw" });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("invitation_invalid");
  });

  it("captures the Retry-After header on 429 responses", async () => {
    const fetchImpl = mockFetch(
      () =>
        new Response(JSON.stringify({ detail: "Too many requests. Please wait a moment and try again." }), {
          status: 429,
          headers: { "content-type": "application/json", "retry-after": "45" },
        }),
    );
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    const result = await client.login({ email: "a@b.com", password: "x".repeat(12) });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("rate_limited");
      expect(result.retryAfterSeconds).toBe(45);
    }
  });

  it("ignores a missing or invalid Retry-After header", async () => {
    for (const retryAfter of [null, "soon", "-5", "0"]) {
      const headers: Record<string, string> = { "content-type": "application/json" };
      if (retryAfter !== null) headers["retry-after"] = retryAfter;
      const fetchImpl = mockFetch(
        () =>
          new Response(JSON.stringify({ detail: "Too many requests." }), {
            status: 429,
            headers,
          }),
      );
      const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
      const result = await client.login({ email: "a@b.com", password: "x".repeat(12) });
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.code).toBe("rate_limited");
        expect(result.retryAfterSeconds).toBeUndefined();
      }
    }
  });

  it("creates a salon with name and slug", async () => {
    const seen: { url: string; body: unknown }[] = [];
    const fetchImpl = mockFetch((url, init) => {
      seen.push({ url, body: JSON.parse(init.body as string) });
      return jsonResponse(201, { id: "s1", name: "Glow", slug: "glow", status: "onboarding" });
    });
    const client = new BackendClient({ baseUrl: "https://api.test", fetchImpl });
    const result = await client.createSalon("at", { name: "Glow", slug: "glow" });
    expect(result.ok).toBe(true);
    expect(seen[0].url).toBe("https://api.test/salons");
    expect(seen[0].body).toEqual({ name: "Glow", slug: "glow" });
  });
});
