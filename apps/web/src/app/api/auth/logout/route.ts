/**
 * BFF: POST /api/auth/logout
 *
 * Calls the backend logout contract (best-effort revocation of the current
 * session), then expires the HttpOnly session cookies. The browser session
 * ends even if the backend call fails — fail secure, never fail open.
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

  if (tokens.accessToken) {
    try {
      await backend.logout(tokens.accessToken);
    } catch {
      // Best-effort: cookie expiry below still ends the browser session.
    }
  }

  const res = NextResponse.json({ ok: true }, { status: 200 });
  clearAuthCookies(res);
  return res;
}
