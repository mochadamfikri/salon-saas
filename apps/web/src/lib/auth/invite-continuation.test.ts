import { describe, expect, it, vi } from "vitest";

import {
  consumeInviteContinuation,
  createInviteContinuation,
  inviteContinuationSize,
} from "./invite-continuation";

describe("invite continuation vault", () => {
  it("parks a token and consumes it exactly once", () => {
    const nonce = createInviteContinuation("raw-token-123");
    expect(typeof nonce).toBe("string");
    expect(nonce.length).toBeGreaterThan(0);

    expect(consumeInviteContinuation(nonce)).toBe("raw-token-123");
    // Single use: the second consume finds nothing.
    expect(consumeInviteContinuation(nonce)).toBeNull();
  });

  it("returns null for unknown nonces", () => {
    expect(consumeInviteContinuation("not-a-real-nonce")).toBeNull();
  });

  it("never exposes the raw token through the nonce", () => {
    const nonce = createInviteContinuation("super-secret-token");
    expect(nonce).not.toContain("super-secret-token");
    expect(inviteContinuationSize()).toBeGreaterThanOrEqual(1);
    consumeInviteContinuation(nonce);
  });

  it("expires parked tokens", () => {
    vi.useFakeTimers();
    try {
      const nonce = createInviteContinuation("expiring-token");
      vi.advanceTimersByTime(11 * 60 * 1000);
      expect(consumeInviteContinuation(nonce)).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});
