/**
 * BFF: POST /api/auth/login
 *
 * Browser -> this handler -> FastAPI POST /auth/login.
 * On success the backend token pair is stored in HttpOnly cookies and the
 * response carries only the safe user profile — tokens never reach the browser.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  bffErrorResponse,
  createBackendClient,
  setAuthCookies,
} from "@/lib/auth/bff";
import { uiMessageFor } from "@/lib/auth/ui-messages";
import { validateEmail } from "@/lib/auth/validation";

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
      { status: 400 },
    );
  }
  if (!password) {
    return NextResponse.json(
      { ok: false, code: "validation_error", message: "Password is required.", field: "password" },
      { status: 400 },
    );
  }

  const backend = createBackendClient();
  const login = await backend.login({ email, password });
  if (!login.ok) {
    // Generic message: no user-enumeration oracle.
    return bffErrorResponse(login.code, uiMessageFor(login.code));
  }

  // Load the safe user profile for the response (tokens stay server-side).
  const me = await backend.getMe(login.data.access_token);
  if (!me.ok) {
    return bffErrorResponse("unknown_error", uiMessageFor("unknown_error"));
  }

  const res = NextResponse.json({ ok: true, user: me.data }, { status: 200 });
  setAuthCookies(res, login.data);
  return res;
}
