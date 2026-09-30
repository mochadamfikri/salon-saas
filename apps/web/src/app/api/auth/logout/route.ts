/**
 * BFF: POST /api/auth/logout
 *
 * Calls the backend logout contract (best-effort revocation of the current
 * session), then expires the HttpOnly session cookies. The browser session
 * ends even if the backend call fails — fail secure, never fail open.
 *
 * When the short-lived access cookie is already gone but the refresh cookie
 * survives, one refresh is attempted first so the backend session can still
 * be revoked server-side. Cookie expiry below always ends the browser
 * session regardless.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  clearAuthCookies,
  createBackendClient,
  getRequestTokens,
} from "@/lib/auth/bff";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const tokens = getRequestTokens(req);
  const backend = createBackendClient();

  let accessToken = tokens.accessToken;
  if (!accessToken && tokens.refreshToken) {
    // Single refresh attempt so a live backend session can be revoked.
    const rotated = await backend.refresh({ refresh_token: tokens.refreshToken });
    if (rotated.ok) accessToken = rotated.data.access_token;
  }

  if (accessToken) {
    try {
      await backend.logout(accessToken);
    } catch {
      // Best-effort: cookie expiry below still ends the browser session.
    }
  }

  const res = NextResponse.json({ ok: true }, { status: 200 });
  clearAuthCookies(res);
  return res;
}
