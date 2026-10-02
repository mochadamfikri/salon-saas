import { NextRequest, NextResponse } from "next/server";
import type { BackendResult } from "@/lib/auth/backend";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
import { updateServicePayload, validateServicePatch } from "@/lib/service-catalog";

type Context = { params: Promise<{ salonId: string; serviceId: string }> };
function failure(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) {
  const response = bffErrorResponse(result.code, errorMessageFor(result.code, result.retryAfterSeconds));
  applySessionOutcome(response, outcome);
  return response;
}
async function jsonBody(req: NextRequest): Promise<Record<string, unknown> | null> {
  try { const value: unknown = await req.json(); return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null; }
  catch { return null; }
}
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId, serviceId } = await params;
  const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.getService(token, salonId, serviceId));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, service: outcome.result.data });
  applySessionOutcome(response, outcome);
  return response;
}
export async function PATCH(req: NextRequest, { params }: Context) {
  const { salonId, serviceId } = await params;
  const body = await jsonBody(req);
  if (!body) return bffErrorResponse("validation_error", "Isi formulir layanan dengan benar.", undefined, 422);
  const errors = validateServicePatch(body);
  if (Object.keys(errors).length) return bffErrorResponse("validation_error", "Periksa kembali data layanan.", { fields: errors }, 422);
  const payload = updateServicePayload(body);
  if (!payload) return bffErrorResponse("validation_error", "Tidak ada perubahan layanan.", undefined, 422);
  const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.updateService(token, salonId, serviceId, payload));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, service: outcome.result.data });
  applySessionOutcome(response, outcome);
  return response;
}
