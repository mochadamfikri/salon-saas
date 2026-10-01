import { NextRequest, NextResponse } from "next/server";
import type { BackendResult } from "@/lib/auth/backend";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
type Context = { params: Promise<{ salonId: string; profileId: string; serviceId: string }> };
function failed(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) { const response = bffErrorResponse(result.code, errorMessageFor(result.code), undefined, result.status); applySessionOutcome(response, outcome); return response; }
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId, profileId, serviceId } = await params; const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.assignStaffService(token, salonId, profileId, serviceId));
  if (!outcome.result.ok) return failed(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, assignment: outcome.result.data }, { status: 201 }); applySessionOutcome(response, outcome); return response;
}
export async function DELETE(req: NextRequest, { params }: Context) {
  const { salonId, profileId, serviceId } = await params; const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.unassignStaffService(token, salonId, profileId, serviceId));
  if (!outcome.result.ok) return failed(outcome.result, outcome);
  const response = NextResponse.json({ ok: true }); applySessionOutcome(response, outcome); return response;
}
