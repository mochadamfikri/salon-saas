import { NextRequest, NextResponse } from "next/server";
import {
  applySessionOutcome,
  authorizedCall,
  bffErrorResponse,
  createBackendClient,
} from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";

type Context = { params: Promise<{ salonId: string }> };

function finish(
  outcome: Awaited<ReturnType<typeof authorizedCall<unknown>>>,
  key: string,
) {
  if (!outcome.result.ok) {
    const res = bffErrorResponse(
      outcome.result.code,
      errorMessageFor(
        outcome.result.code,
        outcome.result.retryAfterSeconds,
      ),
    );
    applySessionOutcome(res, outcome);
    return res;
  }

  const res = NextResponse.json(
    { ok: true, [key]: outcome.result.data },
    { status: 200 },
  );
  applySessionOutcome(res, outcome);
  return res;
}

function isJsonObject(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

export async function GET(
  req: NextRequest,
  { params }: Context,
) {
  const { salonId } = await params;
  const backend = createBackendClient();

  return finish(
    await authorizedCall(
      { backend, req },
      (token) => backend.listStaffProfiles(token, salonId),
    ),
    "profiles",
  );
}

export async function POST(
  req: NextRequest,
  { params }: Context,
) {
  const { salonId } = await params;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return bffErrorResponse(
      "validation_error",
      "Pilih anggota yang valid.",
      undefined,
      422,
    );
  }

  if (
    !isJsonObject(body) ||
    typeof body.membership_id !== "string"
  ) {
    return bffErrorResponse(
      "validation_error",
      "Pilih anggota yang valid.",
      undefined,
      422,
    );
  }

  const membershipId = body.membership_id;
  const backend = createBackendClient();
  const outcome = await authorizedCall(
    { backend, req },
    (token) =>
      backend.createStaffProfile(
        token,
        salonId,
        membershipId,
      ),
  );

  if (!outcome.result.ok) {
    const res = bffErrorResponse(
      outcome.result.code,
      errorMessageFor(
        outcome.result.code,
        outcome.result.retryAfterSeconds,
      ),
    );
    applySessionOutcome(res, outcome);
    return res;
  }

  const res = NextResponse.json(
    { ok: true, profile: outcome.result.data },
    { status: 201 },
  );
  applySessionOutcome(res, outcome);
  return res;
}
