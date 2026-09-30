import { describe, expect, it } from "vitest";

import { invitationStateFor, uiMessageFor } from "./ui-messages";

describe("uiMessageFor", () => {
  it("uses a generic message for invalid credentials (no enumeration)", () => {
    expect(uiMessageFor("invalid_credentials")).toBe("Invalid email or password.");
    expect(uiMessageFor("invalid_credentials")).not.toContain("exists");
  });

  it("never leaks token material in messages", () => {
    const all = [
      "invalid_credentials",
      "invalid_refresh_token",
      "email_taken",
      "slug_taken",
      "unknown_error",
    ] as const;
    for (const code of all) {
      const msg = uiMessageFor(code).toLowerCase();
      expect(msg).not.toContain("access_token");
      expect(msg).not.toContain("refresh_token");
      expect(msg).not.toContain("bearer");
    }
  });

  it("covers every backend error code with a non-empty message", () => {
    const codes = [
      "invalid_credentials",
      "account_inactive",
      "email_taken",
      "invalid_refresh_token",
      "slug_taken",
      "salon_not_found",
      "invitation_invalid",
      "invitation_expired",
      "invitation_revoked",
      "invitation_already_accepted",
      "invitation_email_mismatch",
      "invitation_unavailable",
      "validation_error",
      "unauthorized",
      "forbidden",
      "not_found",
      "rate_limited",
      "network_error",
      "unknown_error",
    ] as const;
    for (const code of codes) {
      expect(uiMessageFor(code).length).toBeGreaterThan(0);
    }
  });
});

describe("invitationStateFor", () => {
  it("maps backend codes to invitation UI states", () => {
    expect(invitationStateFor("invitation_expired")).toBe("expired");
    expect(invitationStateFor("invitation_revoked")).toBe("revoked");
    expect(invitationStateFor("invitation_already_accepted")).toBe("already_accepted");
    expect(invitationStateFor("invitation_email_mismatch")).toBe("email_mismatch");
    expect(invitationStateFor("invitation_invalid")).toBe("invalid");
    expect(invitationStateFor("unauthorized")).toBe("login_required");
    expect(invitationStateFor("invitation_unavailable")).toBe("error");
    expect(invitationStateFor("network_error")).toBe("error");
  });
});
