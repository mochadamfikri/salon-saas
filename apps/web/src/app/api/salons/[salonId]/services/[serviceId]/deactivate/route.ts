import { NextRequest, NextResponse } from "next/server";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";

type Context = { params: Promise<{ salonId: string; serviceId: string }> };
export async function POST(req: NextRequest, { params }: Context) {
  const { salonId, serviceId } = await params;
  const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (token) => backend.setServiceActive(token, salonId, serviceId, false));
  if (!outcome.result.ok) {
    const response = bffErrorResponse(outcome.result.code, errorMessageFor(outcome.result.code, outcome.result.retryAfterSeconds));
    applySessionOutcome(response, outcome);
    return response;
  }
  const response = NextResponse.json({ ok: true, service: outcome.result.data });
  applySessionOutcome(response, outcome);
  return response;
}
