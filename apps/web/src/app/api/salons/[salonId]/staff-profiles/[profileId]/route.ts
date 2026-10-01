import { NextRequest, NextResponse } from "next/server";
import type { BackendResult } from "@/lib/auth/backend";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";

type Context = { params: Promise<{ salonId: string; profileId: string }> };
function failed(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) { const response = bffErrorResponse(result.code, errorMessageFor(result.code), undefined, result.status); applySessionOutcome(response, outcome); return response; }
async function body(req: NextRequest) { try { const parsed: unknown = await req.json(); return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null; } catch { return null; } }
export async function PATCH(req: NextRequest, { params }: Context) {
  const { salonId, profileId } = await params; const input = await body(req);
  if (!input || Object.keys(input).some((key) => !["display_name", "phone", "bio", "photo_url"].includes(key)) || Object.values(input).some((value) => value !== null && typeof value !== "string")) return bffErrorResponse("validation_error", "Periksa kembali data profil.", undefined, 422);
  const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.updateStaffProfile(token, salonId, profileId, input));
  if (!outcome.result.ok) return failed(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, profile: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId, profileId } = await params; const input = await body(req);
  if (typeof input?.is_bookable !== "boolean" || Object.keys(input).length !== 1) return bffErrorResponse("validation_error", "Status profil tidak valid.", undefined, 422);
  const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.toggleStaffBookable(token, salonId, profileId, input.is_bookable as boolean));
  if (!outcome.result.ok) return failed(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, profile: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
