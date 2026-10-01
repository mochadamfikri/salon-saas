import { NextRequest, NextResponse } from "next/server";
import type { BackendResult } from "@/lib/auth/backend";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";

type Context = { params: Promise<{ salonId: string; customerId: string }> };
function failure(result: Extract<BackendResult<unknown>, { ok: false }>, outcome: Parameters<typeof applySessionOutcome>[1]) {
  const response = bffErrorResponse(result.code, errorMessageFor(result.code, result.retryAfterSeconds)); applySessionOutcome(response, outcome); return response;
}
async function bodyOf(req: NextRequest): Promise<Record<string, unknown> | null> {
  try { const body: unknown = await req.json(); return body !== null && typeof body === "object" && !Array.isArray(body) ? body as Record<string, unknown> : null; } catch { return null; }
}
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId, customerId } = await params; const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.getCustomer(token, salonId, customerId));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, customer: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
export async function PATCH(req: NextRequest, { params }: Context) {
  const input = await bodyOf(req);
  if (!input || !Object.keys(input).length) return bffErrorResponse("validation_error", "Tidak ada perubahan pelanggan.", undefined, 422);
  const body: Record<string, unknown> = {};
  const errors: Record<string, string> = {};
  if ("full_name" in input) {
    if (typeof input.full_name !== "string" || !input.full_name.trim()) errors.full_name = "Nama wajib diisi.";
    else body.full_name = input.full_name.trim();
  }
  for (const field of ["email", "phone", "notes"]) if (field in input) {
    const value = input[field];
    if (value !== null && typeof value !== "string") errors[field] = "Nilai tidak valid.";
    else if (typeof value === "string") body[field] = field === "email" ? value.trim().toLowerCase() || null : value.trim() || null;
    else body[field] = null;
  }
  if (Object.keys(errors).length) return bffErrorResponse("validation_error", "Periksa kembali data pelanggan.", { fields: errors }, 422);
  const { salonId, customerId } = await params; const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.updateCustomer(token, salonId, customerId, body));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, customer: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
