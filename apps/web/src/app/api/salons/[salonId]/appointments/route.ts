import { NextRequest, NextResponse } from "next/server";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
import type { BackendResult } from "@/lib/auth/backend";
import type { BackendAppointmentCreate } from "@/lib/auth/contracts";

type Context = { params: Promise<{ salonId: string }> };
function failure(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) { const response = bffErrorResponse(result.code, errorMessageFor(result.code, result.retryAfterSeconds)); applySessionOutcome(response, outcome); return response; }
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId } = await params; const query = new URLSearchParams();
  for (const key of ["starts_at_gte", "starts_at_lte", "staff_profile_id", "customer_id", "service_id", "status", "offset", "limit"]) { const value = req.nextUrl.searchParams.get(key); if (value) query.set(key, value); }
  const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.listAppointments(token, salonId, query));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, appointments: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId } = await params; let body: BackendAppointmentCreate;
  try { body = await req.json(); } catch { return bffErrorResponse("validation_error", "Periksa data janji temu.", undefined, 422); }
  if (!body || typeof body !== "object" || !body.customer_id || !body.service_id || !body.staff_profile_id || !body.starts_at || !body.timezone || Object.keys(body).some((key) => !["customer_id", "service_id", "staff_profile_id", "starts_at", "timezone", "notes"].includes(key))) return bffErrorResponse("validation_error", "Periksa data janji temu.", undefined, 422);
  const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.createAppointment(token, salonId, body));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, appointment: outcome.result.data }, { status: 201 }); applySessionOutcome(response, outcome); return response;
}
