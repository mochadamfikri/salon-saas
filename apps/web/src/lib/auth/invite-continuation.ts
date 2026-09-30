/**
 * Server-side ephemeral parking for raw invitation tokens (Redis-backed).
 *
 * Problem: an invitation link carries its raw bearer token in `?token=`.
 * When the visitor is not authenticated yet, the login/register flow must
 * not receive that token (no token in auth URLs, cookies, storage, or
 * client props — per the Phase 1 security contract), yet the invitation has
 * to continue after login.
 *
 * Solution: the proxy parks the raw token in a SHARED server-side store
 * under a random nonce, sets an HttpOnly cookie holding only the nonce
 * (`salon_ic`), and redirects to /login?next=/invite/accept. The invite
 * page then consumes the nonce (single use), performs the accept
 * server-side, and renders the result — the raw token never leaves the
 * server.
 *
 * Store architecture (F-2):
 * - Redis-backed nonce store, shared across processes/workers/instances.
 *   A module-level Map is NOT acceptable: the proxy and Server Components
 *   are not guaranteed to run in the same process/worker, and process-local
 *   state is lost on restart/scale.
 * - Nonce: `crypto.randomUUID()` (unpredictable, never derived from the token).
 * - TTL: 10 minutes (`INVITE_CONTINUATION_MAX_AGE`), enforced by Redis PX.
 * - Single-use: consume is an atomic Lua GET+DEL — concurrent consumers
 *   cannot both redeem the same nonce.
 * - The browser only ever receives the nonce (HttpOnly cookie). The raw
 *   token never enters URLs, client props, localStorage, sessionStorage,
 *   IndexedDB, or browser-readable cookies, and is never logged.
 * - Fail-closed: Redis failures surface as "no continuation" (the user
 *   re-opens the invite link → graceful `missing_token` state), never as
 *   leaked or half-parked state.
 *
 * Configuration follows the Phase 1 Redis architecture: `REDIS_URL`
 * (e.g. `redis://localhost:6379/0`), same variable the backend uses.
 */

import "server-only";

import { Redis } from "ioredis";

import { INVITE_CONTINUATION_MAX_AGE } from "./cookies";

/** Invitation continuation lifetime: 10 minutes. */
const TTL_MS = INVITE_CONTINUATION_MAX_AGE * 1000;
const KEY_PREFIX = "salon:invite-continuation:";
/** Park retries on nonce collision (cryptographically negligible, guarded anyway). */
const PARK_ATTEMPTS = 3;

/**
 * Atomic single-use consume: returns the parked token and deletes the key
 * in one step, so two concurrent consumers cannot both redeem the nonce.
 */
const CONSUME_LUA = `
local v = redis.call('GET', KEYS[1])
if v then
  redis.call('DEL', KEYS[1])
  return v
else
  return nil
end
`;

export interface InviteContinuationStore {
  /** Park a raw token; resolves with the nonce to hand to the browser. */
  park(token: string): Promise<string>;
  /**
   * Atomically consume a nonce exactly once. Resolves with the parked token,
   * or null when the nonce is unknown, expired, or already used.
   */
  consume(nonce: string): Promise<string | null>;
}

function redisUrl(): string {
  return process.env.REDIS_URL ?? "redis://localhost:6379/0";
}

let sharedClient: Redis | null = null;

/** Lazily-created shared Redis client. Never logs token material on error. */
function sharedRedis(): Redis {
  if (!sharedClient) {
    sharedClient = new Redis(redisUrl(), {
      lazyConnect: true,
      // Fail fast: invitation continuation degrades gracefully when Redis
      // is unreachable; it must never hang request handling.
      connectTimeout: 3000,
      commandTimeout: 3000,
      maxRetriesPerRequest: 2,
      enableReadyCheck: true,
    });
    sharedClient.on("error", () => {
      // Swallowed intentionally: park/consume surface failures to their
      // callers, which degrade to the missing_token state. Logging here
      // must never include token material.
    });
  }
  return sharedClient;
}

/** Production store: Redis-backed, shared across all server processes. */
export class RedisInviteContinuationStore implements InviteContinuationStore {
  async park(token: string): Promise<string> {
    const redis = sharedRedis();
    for (let attempt = 0; attempt < PARK_ATTEMPTS; attempt++) {
      const nonce = globalThis.crypto.randomUUID();
      // NX: never overwrite an existing nonce; PX: 10-minute TTL.
      const set = await redis.set(`${KEY_PREFIX}${nonce}`, token, "PX", TTL_MS, "NX");
      if (set === "OK") return nonce;
    }
    throw new Error("invite continuation: nonce collision, could not park token");
  }

  async consume(nonce: string): Promise<string | null> {
    if (!nonce) return null;
    const redis = sharedRedis();
    const value: unknown = await redis.eval(CONSUME_LUA, 1, `${KEY_PREFIX}${nonce}`);
    return typeof value === "string" ? value : null;
  }
}

let storeOverride: InviteContinuationStore | undefined;

/**
 * Override the active store (tests only). Production always uses the
 * Redis-backed store — never process-local memory.
 */
export function setInviteContinuationStore(store: InviteContinuationStore | undefined): void {
  storeOverride = store;
}

function activeStore(): InviteContinuationStore {
  return storeOverride ?? new RedisInviteContinuationStore();
}

/**
 * Park a raw invitation token. Resolves with the nonce to hand to the
 * browser (HttpOnly cookie). Rejects when the store is unavailable — the
 * caller degrades gracefully (no continuation cookie is set).
 */
export function createInviteContinuation(token: string): Promise<string> {
  return activeStore().park(token);
}

/**
 * Consume a parked token exactly once. Resolves with the token, or null
 * when the nonce is unknown, expired, already used, or the store is
 * unavailable (fail-closed).
 */
export async function consumeInviteContinuation(nonce: string): Promise<string | null> {
  try {
    return await activeStore().consume(nonce);
  } catch {
    return null;
  }
}
