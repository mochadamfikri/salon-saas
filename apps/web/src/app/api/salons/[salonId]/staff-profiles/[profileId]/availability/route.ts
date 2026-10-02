import { NextRequest, NextResponse } from "next/server";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
import type { BackendAvailabilityWrite } from "@/lib/auth/contracts";

type Context = { params: Promise<{ salonId: string; profileId: string }> };
const fields = ["day_of_week", "start_time", "end_time"] as const;
function valid(body: unknown): body is BackendAvailabilityWrite {
  if (!body || typeof body !== "object" || Array.isArray(body)) return false;
  const record = body as Record<string, unknown>;
  if (!Object.keys(record).length || Object.keys(record).some((key) => !fields.includes(key as typeof fields[number]))) return false;
  if ("day_of_week" in record && (!Number.isInteger(record.day_of_week) || Number(record.day_of_week) < 0 || Number(record.day_of_week) > 6)) return false;
  for (const key of ["start_time", "end_time"] as const) if (key in record && (typeof record[key] !== "string" || !/^([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?$/.test(record[key] as string))) return false;
  return !(("start_time" in record && record.start_time === null) || ("end_time" in record && record.end_time === null));
}
function respond(req: NextRequest, outcome: Awaited<ReturnType<typeof authorizedCall<unknown>>>, key = "availability") {
  if (!outcome.result.ok) { const res = bffErrorResponse(outcome.result.code, errorMessageFor(outcome.result.code, outcome.result.retryAfterSeconds)); applySessionOutcome(res, outcome); return res; }
  const res = key === "deleted" ? new NextResponse(null, { status: 204 }) : NextResponse.json({ ok: true, [key]: outcome.result.data });
  applySessionOutcome(res, outcome); return res;
}
export async function GET(req: NextRequest, { params }: Context) { const { salonId, profileId } = await params; const backend = createBackendClient(); return respond(req, await authorizedCall({ backend, req }, (token) => backend.listAvailability(token, salonId, profileId)), "slots"); }
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId, profileId } = await params; let body: unknown;
  try { body = await req.json(); } catch { return bffErrorResponse("validation_error", "Periksa jadwal yang dimasukkan.", undefined, 422); }
  if (!valid(body) || !("day_of_week" in body) || !("start_time" in body) || !("end_time" in body) || body.start_time! >= body.end_time!) return bffErrorResponse("validation_error", "Periksa hari dan rentang waktu.", undefined, 422);
  const backend = createBackendClient(); return respond(req, await authorizedCall({ backend, req }, (token) => backend.createAvailability(token, salonId, profileId, body)), "slot");
}
