/**
 * Server-only session helpers for React Server Components.
 *
 * Uses `next/headers` cookies (read-only in Server Components) to load the
 * current user from the backend. Fails securely: any problem -> null, and
 * callers redirect to /login. Refresh rotation lives in `proxy.ts` and the
 * BFF routes — Server Components never mint or persist tokens.
 */

import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { BackendClient } from "./backend";
import { createBackendClient } from "./bff";
import { ACCESS_COOKIE, decodeCookieValue } from "./cookies";
import type { BackendMySalon, BackendUser } from "./contracts";

async function accessTokenFromCookies(): Promise<string | undefined> {
  const store = await cookies();
  return decodeCookieValue(store.get(ACCESS_COOKIE)?.value);
}

function client(): BackendClient {
  return createBackendClient();
}

/**
 * Return the authenticated backend user, or null when there is no usable
 * session. Never throws for auth problems.
 */
export async function getCurrentUser(): Promise<BackendUser | null> {
  const accessToken = await accessTokenFromCookies();
  if (!accessToken) return null;
  try {
    const result = await client().getMe(accessToken);
    return result.ok ? result.data : null;
  } catch {
    return null;
  }
}

/** Redirect to /login unless a valid backend session exists. */
export async function requireUser(nextPath?: string): Promise<BackendUser> {
  const user = await getCurrentUser();
  if (!user) {
    redirect(nextPath ? `/login?next=${encodeURIComponent(nextPath)}` : "/login");
  }
  return user;
}

/**
 * Load the user's salon memberships from the backend (`GET /me/salons`).
 * Returns null when the session is unusable; the backend stays authoritative
 * for membership/role — nothing here is cached in the browser.
 */
export async function getMySalons(): Promise<BackendMySalon[] | null> {
  const accessToken = await accessTokenFromCookies();
  if (!accessToken) return null;
  try {
    const result = await client().getMySalons(accessToken);
    return result.ok ? result.data : null;
  } catch {
    return null;
  }
}
