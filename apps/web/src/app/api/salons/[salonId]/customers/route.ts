import { NextRequest, NextResponse } from "next/server";
import type { BackendResult } from "@/lib/auth/backend";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";

type Context = { params: Promise<{ salonId: string }> };
function failure(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) {
  const response = bffErrorResponse(result.code, errorMessageFor(result.code, result.retryAfterSeconds));
  applySessionOutcome(response, outcome);
  return response;
}
async function jsonBody(req: NextRequest): Promise<Record<string, unknown> | null> {
  try { const body: unknown = await req.json(); return body !== null && typeof body === "object" && !Array.isArray(body) ? body as Record<string, unknown> : null; }
  catch { return null; }
}
function validate(body: Record<string, unknown>) {
  const errors: Record<string, string> = {};
  if (typeof body.full_name !== "string" || !body.full_name.trim()) errors.full_name = "Nama wajib diisi.";
  for (const field of ["email", "phone", "notes"]) {
    if (field in body && body[field] !== null && typeof body[field] !== "string") errors[field] = "Nilai tidak valid.";
  }
  return errors;
}
function normalized(body: Record<string, unknown>) {
  const result: Record<string, unknown> = { full_name: (body.full_name as string).trim() };
  if ("email" in body) result.email = typeof body.email === "string" ? body.email.trim().toLowerCase() || null : body.email;
  for (const field of ["phone", "notes"]) if (field in body) result[field] = typeof body[field] === "string" ? (body[field] as string).trim() || null : body[field];
  return result;
}
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId } = await params; const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.listCustomers(token, salonId));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, customers: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId } = await params; const body = await jsonBody(req);
  if (!body) return bffErrorResponse("validation_error", "Isi data pelanggan dengan benar.", undefined, 422);
  const errors = validate(body); if (Object.keys(errors).length) return bffErrorResponse("validation_error", "Periksa kembali data pelanggan.", { fields: errors }, 422);
  const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.createCustomer(token, salonId, normalized(body)));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, customer: outcome.result.data }, { status: 201 }); applySessionOutcome(response, outcome); return response;
}
