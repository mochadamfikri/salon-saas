import { NextRequest, NextResponse } from "next/server";
import type { BackendResult } from "@/lib/auth/backend";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
import { customerPayload, validateCustomerInput } from "@/lib/customer-records";

type Context = { params: Promise<{ salonId: string }> };
function failure(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) {
  const response = bffErrorResponse(result.code, errorMessageFor(result.code, result.retryAfterSeconds)); applySessionOutcome(response, outcome); return response;
}
async function body(req: NextRequest): Promise<Record<string, unknown> | null> {
  try { const value: unknown = await req.json(); return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null; } catch { return null; }
}
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId } = await params; const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.listCustomers(token, salonId));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, customers: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId } = await params; const data = await body(req);
  if (!data) return bffErrorResponse("validation_error", "Isi data pelanggan dengan benar.", undefined, 422);
  const errors = validateCustomerInput(data, true);
  if (Object.keys(errors).length) return bffErrorResponse("validation_error", "Periksa kembali data pelanggan.", { fields: errors }, 422);
  const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.createCustomer(token, salonId, customerPayload(data, true)));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, customer: outcome.result.data }, { status: 201 }); applySessionOutcome(response, outcome); return response;
}
