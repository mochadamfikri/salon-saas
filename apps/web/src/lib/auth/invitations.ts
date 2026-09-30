/**
 * Shared invitation-accept orchestration.
 *
 * Used by the BFF route (POST /api/invitations/accept) and by the
 * server-rendered /invite/accept page so both map backend outcomes to the
 * same UI states. The raw token is used once from the caller and never
 * persisted.
 */

import {
  authorizedCallWithTokens,
  createBackendClient,
  type AuthorizedCallOutcome,
} from "./bff";
import type { BackendErrorCode, FetchImpl } from "./backend";
import type { BackendTokenPair } from "./contracts";
import type { SessionTokens } from "./cookies";
import { invitationStateFor, errorMessageFor } from "./ui-messages";
import type { InvitationState } from "./contracts";

export interface InvitationAcceptBody {
  ok: boolean;
  state: InvitationState;
  code?: BackendErrorCode;
  message?: string;
  membership?: { id: string; role: string; status: string };
  salon?: { id: string; name: string; slug: string };
}

export interface InvitationAcceptOutcome {
  httpStatus: number;
  body: InvitationAcceptBody;
  /** Session could not be refreshed — the caller must clear auth cookies. */
  sessionInvalidated: boolean;
  /** Fresh token pair — the caller must persist it (routes only; pages can't set cookies). */
  refreshedTokens?: BackendTokenPair;
}

export interface AcceptInvitationOptions {
  fetchImpl?: FetchImpl;
  /**
   * When false, no refresh rotation is attempted. Server Components MUST
   * pass false: they cannot persist a rotated pair, and with rotating
   * refresh tokens + reuse detection an unpersisted rotation strands the
   * browser with a dead refresh token (F-3). Route Handlers (which persist
   * via setAuthCookies) leave this true.
   */
  allowRefresh?: boolean;
}

export async function acceptInvitationOutcome(
  tokens: SessionTokens,
  rawToken: string,
  options?: AcceptInvitationOptions,
): Promise<InvitationAcceptOutcome> {
  const backend = createBackendClient(options?.fetchImpl);
  const call: AuthorizedCallOutcome<{
    membership?: InvitationAcceptBody["membership"];
    salon?: InvitationAcceptBody["salon"];
  }> = await authorizedCallWithTokens(
    { backend, tokens, allowRefresh: options?.allowRefresh },
    (accessToken) => backend.acceptInvitation(accessToken, { token: rawToken }),
  );

  const session: Pick<InvitationAcceptOutcome, "sessionInvalidated" | "refreshedTokens"> = {
    sessionInvalidated: call.sessionInvalidated ?? false,
    refreshedTokens: call.refreshedTokens,
  };

  if (call.result.ok) {
    return {
      httpStatus: 200,
      ...session,
      body: {
        ok: true,
        state: "success",
        membership: call.result.data.membership,
        salon: call.result.data.salon,
      },
    };
  }

  const code = call.result.code;
  if (code === "unauthorized" && !call.sessionInvalidated) {
    // No session tokens at all — the UI must ask the user to log in.
    return {
      httpStatus: 401,
      ...session,
      body: {
        ok: false,
        state: "login_required",
        code,
        message: "Please log in to accept this invitation.",
      },
    };
  }
  if (call.sessionInvalidated) {
    return {
      httpStatus: 401,
      ...session,
      body: {
        ok: false,
        state: "login_required",
        code: "invalid_refresh_token",
        message: "Your session has expired. Please log in again.",
      },
    };
  }
  if (code === "network_error") {
    return {
      httpStatus: 502,
      ...session,
      body: { ok: false, state: "error", code, message: errorMessageFor(code) },
    };
  }
  return {
    httpStatus: code === "invitation_unavailable" ? 503 : call.result.status,
    ...session,
    body: {
      ok: false,
      state: invitationStateFor(code),
      code,
      message: errorMessageFor(code, call.result.retryAfterSeconds),
    },
  };
}
