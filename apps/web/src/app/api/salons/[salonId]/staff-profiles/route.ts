import { NextRequest, NextResponse } from "next/server";
import type { BackendResult } from "@/lib/auth/backend";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";

type Context = { params: Promise<{ salonId: string }> };
function failed(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) {
  const response = bffErrorResponse(result.code, errorMessageFor(result.code), undefined, result.status);
  applySessionOutcome(response, outcome);
  return response;
}
async function body(req: NextRequest) {
  try { const parsed: unknown = await req.json(); return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null; }
  catch { return null; }
}
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId } = await params; const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, async (token) => {
    const profiles = await backend.listStaffProfiles(token, salonId);
    if (!profiles.ok) return profiles;
    const [members, services] = await Promise.all([backend.listMembers(token, salonId), backend.listServices(token, salonId)]);
    if (!members.ok && members.status !== 403) return members;
    if (!services.ok) return services;
    return { ok: true as const, data: { profiles: profiles.data, members: members.ok ? members.data : [], services: services.data }, status: 200 };
  });
  if (!outcome.result.ok) return failed(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, ...outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId } = await params; const input = await body(req);
  if (typeof input?.membership_id !== "string") return bffErrorResponse("validation_error", "Pilih keanggotaan yang valid.", undefined, 422);
  const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.createStaffProfile(token, salonId, input.membership_id as string));
  if (!outcome.result.ok) return failed(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, profile: outcome.result.data }, { status: 201 }); applySessionOutcome(response, outcome); return response;
}
