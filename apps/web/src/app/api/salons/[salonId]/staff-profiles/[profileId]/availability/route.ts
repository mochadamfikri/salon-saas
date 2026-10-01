import { NextRequest, NextResponse } from "next/server";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";

type Context = { params: Promise<{ salonId: string; profileId: string }> };
function failure(result: { code: Parameters<typeof errorMessageFor>[0]; status: number }, outcome: Parameters<typeof applySessionOutcome>[1]) {
  const response = bffErrorResponse(result.code, errorMessageFor(result.code), undefined, result.status);
  applySessionOutcome(response, outcome);
  return response;
}
function validBody(value: unknown): value is { day_of_week: number; start_time: string; end_time: string; is_available?: boolean } {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const input = value as Record<string, unknown>;
  return Object.keys(input).every((key) => ["day_of_week", "start_time", "end_time", "is_available"].includes(key)) &&
    Number.isInteger(input.day_of_week) && Number(input.day_of_week) >= 0 && Number(input.day_of_week) <= 6 &&
    typeof input.start_time === "string" && /^\d{2}:\d{2}(:\d{2})?$/.test(input.start_time) &&
    typeof input.end_time === "string" && /^\d{2}:\d{2}(:\d{2})?$/.test(input.end_time) && input.start_time < input.end_time &&
    (input.is_available === undefined || typeof input.is_available === "boolean");
}
export async function GET(req: NextRequest, { params }: Context) {
  const { salonId, profileId } = await params;
  const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.listStaffAvailability(token, salonId, profileId));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, availability: outcome.result.data });
  applySessionOutcome(response, outcome);
  return response;
}
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId, profileId } = await params;
  let input: unknown;
  try { input = await req.json(); } catch { input = null; }
  if (!validBody(input)) return bffErrorResponse("validation_error", "Periksa hari dan rentang waktu.", undefined, 422);
  const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.createStaffAvailability(token, salonId, profileId, input));
  if (!outcome.result.ok) return failure(outcome.result, outcome);
  const response = NextResponse.json({ ok: true, availability: outcome.result.data }, { status: 201 });
  applySessionOutcome(response, outcome);
  return response;
}
