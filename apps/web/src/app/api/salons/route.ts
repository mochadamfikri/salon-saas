/**
 * BFF: /api/salons
 *
 * GET  -> backend GET /me/salons (memberships of the authenticated user).
 * POST -> backend POST /salons { name, slug } (creates salon + OWNER membership).
 *
 * The backend is authoritative for slug validity, reserved slugs,
 * uniqueness, and OWNER provisioning. The frontend never assumes ownership
 * from a local form state — only from the backend response.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  applySessionOutcome,
  authorizedCall,
  bffErrorResponse,
  createBackendClient,
} from "@/lib/auth/bff";
import { uiMessageFor } from "@/lib/auth/ui-messages";
import { validateSalonName, validateSlug } from "@/lib/auth/validation";

export async function GET(req: NextRequest): Promise<NextResponse> {
  const backend = createBackendClient();

  const outcome = await authorizedCall({ backend, req }, (accessToken) =>
    backend.getMySalons(accessToken),
  );

  if (!outcome.result.ok) {
    const err = bffErrorResponse(outcome.result.code, uiMessageFor(outcome.result.code));
    applySessionOutcome(err, outcome);
    return err;
  }

  const res = NextResponse.json({ ok: true, salons: outcome.result.data }, { status: 200 });
  applySessionOutcome(res, outcome);
  return res;
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return bffErrorResponse("validation_error", "Invalid request body.");
  }

  const record = (body ?? {}) as Record<string, unknown>;
  const name = typeof record.name === "string" ? record.name.trim() : "";
  const slug = typeof record.slug === "string" ? record.slug.trim().toLowerCase() : "";

  const nameCheck = validateSalonName(name);
  if (!nameCheck.valid) {
    return NextResponse.json(
      { ok: false, code: "validation_error", message: nameCheck.error, field: "name" },
      { status: 400 },
    );
  }
  const slugCheck = validateSlug(slug);
  if (!slugCheck.valid) {
    return NextResponse.json(
      { ok: false, code: "validation_error", message: slugCheck.error, field: "slug" },
      { status: 400 },
    );
  }

  const backend = createBackendClient();
  const outcome = await authorizedCall({ backend, req }, (accessToken) =>
    backend.createSalon(accessToken, { name, slug }),
  );

  if (!outcome.result.ok) {
    const err = bffErrorResponse(outcome.result.code, uiMessageFor(outcome.result.code));
    applySessionOutcome(err, outcome);
    return err;
  }

  const res = NextResponse.json({ ok: true, salon: outcome.result.data }, { status: 201 });
  applySessionOutcome(res, outcome);
  return res;
}
