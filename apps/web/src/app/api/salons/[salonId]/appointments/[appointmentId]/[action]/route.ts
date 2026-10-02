import { NextRequest, NextResponse } from "next/server";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
import type { BackendResult } from "@/lib/auth/backend";
type Context = { params: Promise<{ salonId: string; appointmentId: string; action: string }> };
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId, appointmentId, action } = await params;
  if (!["confirm", "complete", "cancel", "no-show"].includes(action)) return bffErrorResponse("not_found", "Janji temu tidak ditemukan.", undefined, 404);
  const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => backend.appointmentAction(token, salonId, appointmentId, action as "confirm" | "complete" | "cancel" | "no-show"));
  if (!outcome.result.ok) { const response = bffErrorResponse((outcome.result as Extract<BackendResult<unknown>, { ok: false }>).code, errorMessageFor((outcome.result as Extract<BackendResult<unknown>, { ok: false }>).code)); applySessionOutcome(response, outcome); return response; }
  const response = NextResponse.json({ ok: true, appointment: outcome.result.data }); applySessionOutcome(response, outcome); return response;
}
