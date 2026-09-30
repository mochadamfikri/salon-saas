/**
 * Backend error codes -> user-facing messages.
 *
 * Security rules:
 * - Generic message for invalid credentials (no user-enumeration oracle).
 * - Never surface raw tokens, session internals, or backend stack details.
 * - Backend `detail` strings are never rendered verbatim.
 */

import type { BackendErrorCode } from "./backend";
import type { InvitationState } from "./contracts";

const MESSAGES: Record<BackendErrorCode, string> = {
  invalid_credentials: "Invalid email or password.",
  account_inactive: "This account is not active. Please contact support.",
  email_taken: "This email is already registered. Try logging in instead.",
  invalid_refresh_token: "Your session has expired. Please log in again.",
  slug_taken: "That salon URL is already taken. Try another one.",
  salon_not_found: "Salon not found.",
  invitation_invalid: "This invitation link is invalid.",
  invitation_expired: "This invitation has expired. Ask for a new one.",
  invitation_revoked: "This invitation was revoked. Ask for a new one.",
  invitation_already_accepted: "This invitation was already accepted.",
  invitation_duplicate_membership:
    "You are already a member of this salon. No need to accept again.",
  invitation_email_mismatch:
    "This invitation was sent to a different email address. Log in with the invited email.",
  invitation_unavailable:
    "Invitations are not enabled yet. Please try again after the backend update.",
  validation_error: "Please check the highlighted fields and try again.",
  unauthorized: "Please log in to continue.",
  forbidden: "You do not have permission to do that.",
  not_found: "The requested resource was not found.",
  rate_limited: "Too many attempts. Please wait a moment and try again.",
  network_error: "Could not reach the server. Check your connection and try again.",
  unknown_error: "Something went wrong. Please try again.",
};

/** UI message for a backend error code. Always returns a safe string. */
export function uiMessageFor(code: BackendErrorCode): string {
  return MESSAGES[code] ?? MESSAGES.unknown_error;
}

/**
 * Sensible user-facing message for a 429 rate-limit response.
 * Uses the backend's `Retry-After` value (seconds) when available so the
 * user knows how long to wait; falls back to the generic message otherwise.
 */
export function rateLimitedMessage(retryAfterSeconds?: number): string {
  if (retryAfterSeconds !== undefined && retryAfterSeconds > 0) {
    if (retryAfterSeconds >= 60) {
      const minutes = Math.round(retryAfterSeconds / 60);
      return `Too many attempts. Please try again in about ${minutes} minute${minutes === 1 ? "" : "s"}.`;
    }
    return `Too many attempts. Please try again in ${retryAfterSeconds} seconds.`;
  }
  return MESSAGES.rate_limited;
}

/**
 * Message for a failed backend call: honors the `Retry-After` hint on
 * 429s, generic safe message otherwise. Prefer this over `uiMessageFor`
 * at call sites that have the backend result in scope.
 */
export function errorMessageFor(
  code: BackendErrorCode,
  retryAfterSeconds?: number,
): string {
  if (code === "rate_limited") return rateLimitedMessage(retryAfterSeconds);
  return uiMessageFor(code);
}

/** InvitationState for a backend error code (used by the invite flow). */
export function invitationStateFor(code: BackendErrorCode): InvitationState {
  switch (code) {
    case "invitation_expired":
      return "expired";
    case "invitation_revoked":
      return "revoked";
    case "invitation_already_accepted":
      return "already_accepted";
    case "invitation_duplicate_membership":
      return "already_member";
    case "invitation_email_mismatch":
      return "email_mismatch";
    case "invitation_invalid":
    case "not_found":
      return "invalid";
    case "unauthorized":
    case "invalid_refresh_token":
      return "login_required";
    case "invitation_unavailable":
      return "error";
    default:
      return "error";
  }
}
