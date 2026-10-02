/**
 * BFF: POST /api/invitations/accept
 *
 * Forwards to the backend's canonical invitation-accept contract
 * (POST /invitations/accept { token } — backend Checkpoint D, live).
 *
 * The raw invitation token is used once from the request body and is never
 * persisted anywhere (no cookies, no storage).
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  applySessionOutcome,
  bffErrorResponse,
  getRequestTokens,
} from "@/lib/auth/bff";
import { acceptInvitationOutcome } from "@/lib/auth/invitations";

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return bffErrorResponse("validation_error", "Invalid request body.");
  }

  const record = (body ?? {}) as Record<string, unknown>;
  const token = typeof record.token === "string" ? record.token.trim() : "";
  if (!token) {
    return NextResponse.json(
      { ok: false, code: "validation_error", message: "Invitation token is required.", field: "token" },
      { status: 422 },
    );
  }

  const outcome = await acceptInvitationOutcome(getRequestTokens(req), token);

  const res = NextResponse.json(outcome.body, { status: outcome.httpStatus });
  applySessionOutcome(res, outcome);
  return res;
}
