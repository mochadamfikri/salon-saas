import { NextRequest, NextResponse } from "next/server";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
import type { BackendResult } from "@/lib/auth/backend";
import type { BackendAppointmentUpdate } from "@/lib/auth/contracts";
type Context = { params: Promise<{ salonId: string; appointmentId: string }> };
function failure(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) { const response = bffErrorResponse(result.code, errorMessageFor(result.code, result.retryAfterSeconds)); applySessionOutcome(response, outcome); return response; }
export async function PATCH(req: NextRequest, { params }: Context) {
  const { salonId, appointmentId } = await params; let body: BackendAppointmentUpdate;
  try { body = await req.json(); } catch { return bffErrorResponse("validation_error", "Periksa data janji temu.", undefined, 422); }
  if (!body || typeof body !== "object" || Array.isArray(body) || !Object.keys(body).length || Object.keys(body).some((key) => !["starts_at", "timezone", "notes"].includes(key)) || (body.starts_at !== undefined && typeof body.starts_at !== "string") || (body.timezone !== undefined && typeof body.timezone !== "string") || (body.notes !== undefined && body.notes !== null && typeof body.notes !== "string")) return bffErrorResponse("validation_error", "Periksa data janji temu.", undefined, 422);
  const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.updateAppointment(token, salonId, appointmentId, body));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, appointment: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
// Actions are exposed on their dedicated nested route.
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId, appointmentId } = await params; const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.getAppointment(token, salonId, appointmentId));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, appointment: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
