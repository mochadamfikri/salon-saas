/**
 * BFF: POST /api/auth/refresh
 *
 * Explicit session rotation endpoint. Reads the refresh HttpOnly cookie,
 * rotates it against the backend, and re-issues both cookies. The response
 * carries no tokens — only an ok flag.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  bffErrorResponse,
  clearAuthCookies,
  createBackendClient,
  getRequestTokens,
  setAuthCookies,
} from "@/lib/auth/bff";
import { uiMessageFor } from "@/lib/auth/ui-messages";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const tokens = getRequestTokens(req);
  if (!tokens.refreshToken) {
    return bffErrorResponse("unauthorized", uiMessageFor("unauthorized"));
  }

  const backend = createBackendClient();
  const rotated = await backend.refresh({ refresh_token: tokens.refreshToken });

  if (!rotated.ok) {
    const err = bffErrorResponse("invalid_refresh_token", uiMessageFor("invalid_refresh_token"));
    clearAuthCookies(err);
    return err;
  }

  const res = NextResponse.json({ ok: true }, { status: 200 });
  setAuthCookies(res, rotated.data);
  return res;
}
