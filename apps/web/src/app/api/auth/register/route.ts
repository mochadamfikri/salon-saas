/**
 * BFF: POST /api/auth/register
 *
 * Enforces the backend password policy (12..128 chars, unicode-safe, no
 * arbitrary complexity rules) before forwarding to FastAPI. Duplicate emails
 * are reported without leaking whether the address exists beyond the
 * registration attempt itself.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  bffErrorResponse,
  createBackendClient,
  setAuthCookies,
} from "@/lib/auth/bff";
import { errorMessageFor } from "@/lib/auth/ui-messages";
import { validateEmail, validatePassword } from "@/lib/auth/validation";

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return bffErrorResponse("validation_error", "Invalid request body.");
  }

  const record = (body ?? {}) as Record<string, unknown>;
  const email = typeof record.email === "string" ? record.email.trim() : "";
  const password = typeof record.password === "string" ? record.password : "";

  const emailCheck = validateEmail(email);
  if (!emailCheck.valid) {
    return NextResponse.json(
      { ok: false, code: "validation_error", message: emailCheck.error, field: "email" },
      { status: 422 },
    );
  }
  const passwordCheck = validatePassword(password);
  if (!passwordCheck.valid) {
    return NextResponse.json(
      { ok: false, code: "validation_error", message: passwordCheck.error, field: "password" },
      { status: 422 },
    );
  }

  const backend = createBackendClient();
  const registered = await backend.register({ email, password });
  if (!registered.ok) {
    return bffErrorResponse(
      registered.code,
      errorMessageFor(registered.code, registered.retryAfterSeconds),
    );
  }

  const me = await backend.getMe(registered.data.access_token);
  if (!me.ok) {
    return bffErrorResponse("unknown_error", errorMessageFor("unknown_error"));
  }

  const res = NextResponse.json({ ok: true, user: me.data }, { status: 201 });
  setAuthCookies(res, registered.data);
  return res;
}
