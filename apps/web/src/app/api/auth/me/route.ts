/**
 * BFF: GET /api/auth/me
 *
 * Returns the authenticated user profile. Uses single-attempt refresh when
 * the access token is missing/expired; refreshed cookies are set on the
 * response. 401 here means "no usable session" — the UI redirects to login.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  applySessionOutcome,
  authorizedCall,
  bffErrorResponse,
  createBackendClient,
} from "@/lib/auth/bff";
import { uiMessageFor } from "@/lib/auth/ui-messages";

export async function GET(req: NextRequest): Promise<NextResponse> {
  const backend = createBackendClient();

  const outcome = await authorizedCall({ backend, req }, (accessToken) =>
    backend.getMe(accessToken),
  );

  if (!outcome.result.ok) {
    const err = bffErrorResponse(outcome.result.code, uiMessageFor(outcome.result.code));
    applySessionOutcome(err, outcome);
    return err;
  }

  const res = NextResponse.json({ ok: true, user: outcome.result.data }, { status: 200 });
  applySessionOutcome(res, outcome);
  return res;
}
