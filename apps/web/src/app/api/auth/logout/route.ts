/**
 * BFF: POST /api/auth/logout
 *
 * Revocation flow (F-4):
 *  1. If an access token is present, attempt backend logout (revocation)
 *     with it.
 *  2. If that logout reports the access token as expired/unauthorized (401)
 *     and a refresh token is available, perform EXACTLY ONE refresh and
 *     retry the logout with the fresh access token.
 *  3. Browser cookies are ALWAYS cleared afterwards — the browser session
 *     ends even if the backend call fails. Fail secure, never fail open.
 *  4. No loops: at most one refresh, at most two logout attempts.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  clearAuthCookies,
  createBackendClient,
  getRequestTokens,
} from "@/lib/auth/bff";
import type { BackendClient } from "@/lib/auth/backend";

async function attemptRevoke(backend: BackendClient, accessToken: string): Promise<number> {
  try {
    const result = await backend.logout(accessToken);
    return result.ok ? 200 : result.status;
  } catch {
    // Best-effort: cookie expiry below still ends the browser session.
    return 0;
  }
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  const tokens = getRequestTokens(req);
  const backend = createBackendClient();

  if (tokens.accessToken) {
    const status = await attemptRevoke(backend, tokens.accessToken);
    if (status === 401 && tokens.refreshToken) {
      // The access token is stale but the refresh token may still be
      // alive: exactly one rotation, then revoke with the fresh token.
      const rotated = await backend.refresh({ refresh_token: tokens.refreshToken });
      if (rotated.ok) {
        await attemptRevoke(backend, rotated.data.access_token);
      }
    }
  } else if (tokens.refreshToken) {
    // No access cookie left (e.g. it expired client-side): one refresh so
    // the backend session can still be revoked server-side.
    const rotated = await backend.refresh({ refresh_token: tokens.refreshToken });
    if (rotated.ok) {
      await attemptRevoke(backend, rotated.data.access_token);
    }
  }

  const res = NextResponse.json({ ok: true }, { status: 200 });
  clearAuthCookies(res);
  return res;
}
