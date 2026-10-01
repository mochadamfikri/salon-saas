import { NextRequest, NextResponse } from "next/server";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
type Context = { params: Promise<{ salonId: string; profileId: string }> };
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId, profileId } = await params; const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.listStaffAssignments(token, salonId, profileId));
  if (!outcome.result.ok) { const response = bffErrorResponse(outcome.result.code, errorMessageFor(outcome.result.code), undefined, outcome.result.status); applySessionOutcome(response, outcome); return response; }
  const response = NextResponse.json({ ok: true, assignments: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
