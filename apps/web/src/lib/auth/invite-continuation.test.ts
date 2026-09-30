import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The real module is server-only guarded; neutralize the guard in the test
// environment so the store contract itself can be exercised.
vi.mock("server-only", () => ({}));

import {
  consumeInviteContinuation,
  createInviteContinuation,
  RedisInviteContinuationStore,
  setInviteContinuationStore,
  type InviteContinuationStore,
} from "./invite-continuation";

/**
 * Test-only fake implementing the store contract with Redis semantics
 * (TTL + atomic single-use). Production NEVER uses process-local memory —
 * see RedisInviteContinuationStore.
 */
class FakeInviteContinuationStore implements InviteContinuationStore {
  private entries = new Map<string, { token: string; expiresAt: number }>();
  parked: Array<{ nonce: string; token: string }> = [];

  async park(token: string): Promise<string> {
    const nonce = `nonce-${this.parked.length + 1}-${Math.random().toString(36).slice(2)}`;
    this.entries.set(nonce, { token, expiresAt: Date.now() + 10 * 60 * 1000 });
    this.parked.push({ nonce, token });
    return nonce;
  }

  async consume(nonce: string): Promise<string | null> {
    const entry = this.entries.get(nonce);
    this.entries.delete(nonce);
    if (!entry || entry.expiresAt <= Date.now()) return null;
    return entry.token;
  }
}

describe("invite continuation store contract", () => {
  let store: FakeInviteContinuationStore;

  beforeEach(() => {
    store = new FakeInviteContinuationStore();
    setInviteContinuationStore(store);
  });

  afterEach(() => {
    setInviteContinuationStore(undefined);
    vi.useRealTimers();
  });

  it("parks a token and consumes it exactly once", async () => {
    const nonce = await createInviteContinuation("raw-token-123");
    expect(typeof nonce).toBe("string");
    expect(nonce.length).toBeGreaterThan(0);

    expect(await consumeInviteContinuation(nonce)).toBe("raw-token-123");
    // Single use: the second consume finds nothing.
    expect(await consumeInviteContinuation(nonce)).toBeNull();
  });

  it("returns null for unknown nonces", async () => {
    expect(await consumeInviteContinuation("not-a-real-nonce")).toBeNull();
  });

  it("never exposes the raw token through the nonce", async () => {
    const nonce = await createInviteContinuation("super-secret-token");
    expect(nonce).not.toContain("super-secret-token");
    await consumeInviteContinuation(nonce);
  });

  it("expires parked tokens after the TTL", async () => {
    vi.useFakeTimers();
    const nonce = await createInviteContinuation("expiring-token");
    vi.advanceTimersByTime(11 * 60 * 1000);
    expect(await consumeInviteContinuation(nonce)).toBeNull();
  });

  it("fail-closes to null when the store throws", async () => {
    setInviteContinuationStore({
      park: async () => {
        throw new Error("redis down");
      },
      consume: async () => {
        throw new Error("redis down");
      },
    });
    expect(await consumeInviteContinuation("any-nonce")).toBeNull();
    await expect(createInviteContinuation("tok")).rejects.toThrow("redis down");
  });
});

describe("production store wiring", () => {
  it("exposes no process-local vault API (regression guard for F-2)", async () => {
    // The old module-level Map implementation must not come back: these
    // APIs only existed on the process-local vault.
    const mod = await import("./invite-continuation");
    expect("inviteContinuationSize" in mod).toBe(false);
    expect("vault" in mod).toBe(false);
    // The production store class is Redis-backed.
    expect(new RedisInviteContinuationStore()).toBeInstanceOf(RedisInviteContinuationStore);
  });
});
