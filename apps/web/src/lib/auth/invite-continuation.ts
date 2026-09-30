/**
 * Server-side ephemeral parking for raw invitation tokens.
 *
 * Problem: an invitation link carries its raw bearer token in `?token=`.
 * When the visitor is not authenticated yet, the login/register flow must
 * not receive that token (no token in auth URLs, cookies, storage, or
 * client props — per the Phase 1 security contract), yet the invitation has
 * to continue after login.
 *
 * Solution: the proxy parks the raw token in this in-memory vault under a
 * random nonce, sets an HttpOnly cookie holding only the nonce
 * (`salon_ic`), and redirects to /login?next=/invite/accept. The invite
 * page then consumes the nonce (single use), performs the accept
 * server-side, and renders the result — the raw token never leaves the
 * server.
 *
 * Scope notes (Phase 1):
 * - Ephemeral process memory with a 10-minute TTL and single-use consume;
 *   nothing is persisted, satisfying "never persist raw tokens in plaintext".
 * - Single-instance deployment assumption: with multiple server instances a
 *   parked token may not be found after login and the user simply re-opens
 *   the invite link (graceful `missing_token` state, no crash, no leak).
 */

import { INVITE_CONTINUATION_MAX_AGE } from "./cookies";

const TTL_MS = INVITE_CONTINUATION_MAX_AGE * 1000;
const MAX_ENTRIES = 1000;

interface Entry {
  token: string;
  expiresAt: number;
}

const vault = new Map<string, Entry>();

function sweep(): void {
  const now = Date.now();
  for (const [nonce, entry] of vault) {
    if (entry.expiresAt <= now) vault.delete(nonce);
  }
  // Bound memory: drop the oldest entries beyond the cap.
  if (vault.size > MAX_ENTRIES) {
    const excess = vault.size - MAX_ENTRIES;
    const keys = vault.keys();
    for (let i = 0; i < excess; i++) {
      const next = keys.next();
      if (next.done) break;
      vault.delete(next.value);
    }
  }
}

/**
 * Park a raw invitation token. Returns the nonce to hand to the browser
 * (HttpOnly cookie). The token itself stays server-side.
 */
export function createInviteContinuation(token: string): string {
  sweep();
  const nonce = globalThis.crypto.randomUUID();
  vault.set(nonce, { token, expiresAt: Date.now() + TTL_MS });
  return nonce;
}

/**
 * Consume a parked token exactly once. Returns null when the nonce is
 * unknown, expired, or already used.
 */
export function consumeInviteContinuation(nonce: string): string | null {
  const entry = vault.get(nonce);
  vault.delete(nonce);
  if (!entry || entry.expiresAt <= Date.now()) return null;
  return entry.token;
}

/** Test-only: number of live entries. */
export function inviteContinuationSize(): number {
  sweep();
  return vault.size;
}
