import { NextRequest, NextResponse } from "next/server";
import {
  applySessionOutcome,
  authorizedCall,
  bffErrorResponse,
  createBackendClient,
} from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";

function isJsonObject(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

export async function POST(
  req: NextRequest,
  {
    params,
  }: {
    params: Promise<{
      salonId: string;
      profileId: string;
    }>;
  },
) {
  const { salonId, profileId } = await params;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return bffErrorResponse(
      "validation_error",
      "Status profil tidak valid.",
      undefined,
      422,
    );
  }

  if (
    !isJsonObject(body) ||
    typeof body.is_bookable !== "boolean"
  ) {
    return bffErrorResponse(
      "validation_error",
      "Status profil tidak valid.",
      undefined,
      422,
    );
  }

  const isBookable = body.is_bookable;
  const backend = createBackendClient();
  const outcome = await authorizedCall(
    { backend, req },
    (token) =>
      backend.toggleStaffBookable(
        token,
        salonId,
        profileId,
        isBookable,
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

  const res = NextResponse.json({
    ok: true,
    profile: outcome.result.data,
  });
  applySessionOutcome(res, outcome);
  return res;
}
