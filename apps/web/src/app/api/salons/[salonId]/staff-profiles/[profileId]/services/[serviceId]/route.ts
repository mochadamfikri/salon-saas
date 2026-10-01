import { NextRequest, NextResponse } from "next/server";
import { applySessionOutcome, authorizedCall, bffErrorResponse, createBackendClient } from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
type Context = { params: Promise<{ salonId: string; profileId: string; serviceId: string }> };
async function respond(req: NextRequest, params: Context["params"], method: "POST" | "DELETE") { const { salonId, profileId, serviceId } = await params; const backend = createBackendClient(); const outcome = await authorizedCall({ backend, req }, (token) => method === "POST" ? backend.assignStaffService(token, salonId, profileId, serviceId) : backend.unassignStaffService(token, salonId, profileId, serviceId)); if (!outcome.result.ok) { const res = bffErrorResponse(outcome.result.code, errorMessageFor(outcome.result.code, outcome.result.retryAfterSeconds)); applySessionOutcome(res, outcome); return res; } const res = method === "DELETE" ? new NextResponse(null, { status: 204 }) : NextResponse.json({ ok: true, assignment: outcome.result.data }, { status: 201 }); applySessionOutcome(res, outcome); return res; }
export async function POST(req: NextRequest, { params }: Context) { return respond(req, params, "POST"); }
export async function DELETE(req: NextRequest, { params }: Context) { return respond(req, params, "DELETE"); }
