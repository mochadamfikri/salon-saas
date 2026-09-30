/**
 * BFF: POST /api/invitations/accept
 *
 * Forwards to the backend's invitation-accept contract
 * (POST /invitations/accept { token } — backend Checkpoint D, P1-023).
 *
 * Until the backend ships that endpoint this returns code
 * `invitation_unavailable` (503) so the UI can say so plainly.
 * The raw invitation token is used once from the request body and is never
 * persisted anywhere (no cookies, no storage).
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  applySessionOutcome,
  authorizedCall,
  bffErrorResponse,
  createBackendClient,
} from "@/lib/auth/bff";
import { invitationStateFor, uiMessageFor } from "@/lib/auth/ui-messages";

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
      { status: 400 },
    );
  }

  const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (accessToken) =>
    backend.acceptInvitation(accessToken, { token }),
  );

  if (!outcome.result.ok) {
    const code = outcome.result.code;
    const state = invitationStateFor(code);
    const message = uiMessageFor(code);
    const statusOverride = code === "invitation_unavailable" ? 503 : undefined;
    const err = bffErrorResponse(code, message, { state }, statusOverride);
    applySessionOutcome(err, outcome);
    return err;
  }

  const res = NextResponse.json(
    {
      ok: true,
      state: "success" as const,
      membership: outcome.result.data.membership,
      salon: outcome.result.data.salon,
    },
    { status: 200 },
  );
  applySessionOutcome(res, outcome);
  return res;
}
