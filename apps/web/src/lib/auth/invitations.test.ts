import { beforeEach, describe, expect, it, vi } from "vitest";

import { acceptInvitationOutcome } from "./invitations";

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const TOKENS = { accessToken: "at1", refreshToken: "rt1" };
const MEMBERSHIP = { id: "m1", role: "staff", status: "active" };
const SALON = { id: "s1", name: "Glow", slug: "glow" };

describe("acceptInvitationOutcome", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("accepts an invitation and returns membership context", async () => {
    const seen: unknown[] = [];
    const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
      if (String(url).endsWith("/invitations/accept")) {
        seen.push(JSON.parse(init.body as string));
        return jsonResponse(200, { membership: MEMBERSHIP, salon: SALON });
      }
      return jsonResponse(200, { id: "u1" });
    }) as unknown as typeof fetch;

    const outcome = await acceptInvitationOutcome(TOKENS, "raw-token", {
      fetchImpl,
    });
    expect(outcome.httpStatus).toBe(200);
    expect(outcome.body).toMatchObject({
      ok: true,
      state: "success",
      membership: MEMBERSHIP,
      salon: SALON,
    });
    expect(seen).toEqual([{ token: "raw-token" }]);
    expect(outcome.sessionInvalidated).toBe(false);
  });

  it("asks for login when there is no session", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {})) as unknown as typeof fetch;
    const outcome = await acceptInvitationOutcome({ accessToken: undefined, refreshToken: undefined }, "raw-token", {
      fetchImpl,
    });
    expect(outcome.httpStatus).toBe(401);
    expect(outcome.body.state).toBe("login_required");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("maps backend invitation states", async () => {
    const cases: Array<[number, string, number, string]> = [
      [404, "Invitation not found", 404, "invalid"],
      [410, "Invitation expired", 410, "expired"],
      [410, "Invitation revoked", 410, "revoked"],
      [409, "Invitation already accepted", 409, "already_accepted"],
      [422, "Invitation email mismatch", 422, "email_mismatch"],
    ];
    for (const [backendStatus, detail, expectedStatus, expectedState] of cases) {
      const fetchImpl = vi.fn(async (url: string) => {
        if (String(url).endsWith("/auth/me")) return jsonResponse(200, { id: "u1" });
        return jsonResponse(backendStatus, { detail });
      }) as unknown as typeof fetch;
      const outcome = await acceptInvitationOutcome(TOKENS, "tok", {
      fetchImpl,
    });
      expect(outcome.httpStatus).toBe(expectedStatus);
      expect(outcome.body.state).toBe(expectedState);
      expect(outcome.body.message).toBeTruthy();
    }
  });

  it("reports invitation_unavailable when the backend route is missing", async () => {
    // FastAPI default 404 body when the route does not exist (Checkpoint D pending).
    const fetchImpl = vi.fn(async (url: string) => {
      if (String(url).endsWith("/auth/me")) return jsonResponse(200, { id: "u1" });
      return jsonResponse(404, { detail: "Not Found" });
    }) as unknown as typeof fetch;
    const outcome = await acceptInvitationOutcome(TOKENS, "tok", {
      fetchImpl,
    });
    expect(outcome.httpStatus).toBe(503);
    expect(outcome.body).toMatchObject({ ok: false, state: "error", code: "invitation_unavailable" });
  });

  it("flags sessionInvalidated when refresh fails", async () => {
    const fetchImpl = vi.fn(async (url: string) => {
      if (String(url).endsWith("/invitations/accept")) {
        return jsonResponse(401, { detail: "Token has expired" });
      }
      if (String(url).endsWith("/auth/refresh")) {
        return jsonResponse(401, { detail: "Invalid or revoked refresh token" });
      }
      return jsonResponse(404, {});
    }) as unknown as typeof fetch;
    const outcome = await acceptInvitationOutcome(TOKENS, "tok", {
      fetchImpl,
    });
    expect(outcome.httpStatus).toBe(401);
    expect(outcome.body.state).toBe("login_required");
    expect(outcome.sessionInvalidated).toBe(true);
  });

  it("surfaces refreshed tokens for the caller to persist", async () => {
    let acceptCalls = 0;
    const fetchImpl = vi.fn(async (url: string) => {
      if (String(url).endsWith("/invitations/accept")) {
        acceptCalls += 1;
        return acceptCalls === 1
          ? jsonResponse(401, { detail: "Token has expired" })
          : jsonResponse(200, { membership: MEMBERSHIP, salon: SALON });
      }
      if (String(url).endsWith("/auth/refresh")) {
        return jsonResponse(200, {
          access_token: "fresh-at",
          refresh_token: "fresh-rt",
          token_type: "bearer",
        });
      }
      return jsonResponse(404, {});
    }) as unknown as typeof fetch;
    const outcome = await acceptInvitationOutcome(TOKENS, "tok", {
      fetchImpl,
    });
    expect(outcome.httpStatus).toBe(200);
    expect(outcome.body.state).toBe("success");
    expect(outcome.refreshedTokens?.access_token).toBe("fresh-at");
  });

  it("with allowRefresh:false never rotates, even when refresh could succeed (F-3)", async () => {
    // The /invite/accept Server Component cannot persist a rotated pair, so
    // it must not trigger a rotation: fail closed instead of stranding the
    // browser with a rotated-out refresh token.
    const seen: string[] = [];
    const fetchImpl = vi.fn(async (url: string) => {
      seen.push(String(url));
      if (String(url).endsWith("/invitations/accept")) {
        return jsonResponse(401, { detail: "Token has expired" });
      }
      if (String(url).endsWith("/auth/refresh")) {
        return jsonResponse(200, {
          access_token: "fresh-at",
          refresh_token: "fresh-rt",
          token_type: "bearer",
        });
      }
      return jsonResponse(404, {});
    }) as unknown as typeof fetch;
    const outcome = await acceptInvitationOutcome(TOKENS, "tok", {
      fetchImpl,
      allowRefresh: false,
    });
    expect(seen.some((u) => u.endsWith("/auth/refresh"))).toBe(false);
    expect(outcome.refreshedTokens).toBeUndefined();
    expect(outcome.sessionInvalidated).toBe(false);
    expect(outcome.httpStatus).toBe(401);
  });

  it("with allowRefresh:false and no access token, does not refresh either", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {})) as unknown as typeof fetch;
    const outcome = await acceptInvitationOutcome(
      { accessToken: undefined, refreshToken: "rt1" },
      "tok",
      { fetchImpl, allowRefresh: false },
    );
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(outcome.body.state).toBe("login_required");
  });
});
