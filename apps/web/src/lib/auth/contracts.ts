/**
 * Typed contracts for the Salon SaaS FastAPI backend (Phase 1).
 *
 * These mirror the backend Pydantic schemas on branch
 * `feature/phase-1-auth-tenancy`. The backend is the source of truth;
 * the frontend must never invent fields the backend does not return.
 *
 * Invitation contracts follow the canonical Checkpoint D accept contract
 * (live on the backend branch); see BackendInvitationAcceptResponse below.
 */

/** POST /auth/register, POST /auth/login, POST /auth/refresh response. */
export interface BackendTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string; // "bearer"
}

/** POST /auth/register request. */
export interface BackendRegisterRequest {
  email: string;
  password: string;
}

/** POST /auth/login request. */
export interface BackendLoginRequest {
  email: string;
  password: string;
}

/** POST /auth/refresh request. */
export interface BackendRefreshRequest {
  refresh_token: string;
}

/** GET /auth/me response. Global user identity (no tenant fields by design). */
export interface BackendUser {
  id: string;
  email: string;
  is_active: boolean;
  is_super_admin: boolean;
}

/** Salon (tenant) representation. */
export interface BackendSalon {
  id: string;
  name: string;
  slug: string;
  status: "onboarding" | "active" | "suspended";
}

/**
 * POST /salons request.
 *
 * Slug is OPTIONAL: when omitted (or blank), the backend auto-generates one
 * and remains the authority for slug validity, reserved slugs, and
 * uniqueness. A provided slug is validated for UX, but the backend decides.
 */
export interface BackendSalonCreateRequest {
  name: string;
  slug?: string;
}

/** Tenant role. `customer` is intentionally NOT a tenant role. */
export type TenantRole = "owner" | "manager" | "staff";

/** Membership representation. */
export interface BackendMembership {
  id: string;
  role: TenantRole;
  status: string;
  user: {
    id: string;
    email: string;
  };
}

/** GET /me/salons response item: membership + salon. */
export interface BackendMySalon {
  id: string;
  role: TenantRole;
  status: string;
  salon: BackendSalon;
}

/**
 * Canonical backend contract (Checkpoint D — implemented and live on
 * `feature/phase-1-auth-tenancy`, verified against backend HEAD 5171a18).
 *
 * Endpoint: POST /invitations/accept
 * Request:  { "token": "<raw invitation token>" }
 *
 * Success (200): the created membership plus salon context.
 * Failures (mapped by backend status + `detail` string):
 *  - 404 "Invalid invitation token"            -> invalid token
 *  - 409 "Invitation has already been accepted"-> already accepted
 *  - 409 "User already has an active membership in this salon"
 *                                              -> duplicate membership
 *  - 410 "Invitation has expired"              -> expired
 *  - 410 "Invitation has been revoked"         -> revoked
 *  - 422 "Invitation email mismatch: ..."      -> invitation email != user email
 *  - 401                                       -> not authenticated
 *  - 429 (with `Retry-After` header, seconds)  -> rate limited
 *
 * The backend never collapses invitation lifecycle failures into a
 * generic 404; the frontend mirrors each outcome with its own UI state.
 */
export interface BackendInvitationAcceptRequest {
  token: string;
}

export interface BackendInvitationAcceptResponse {
  membership: BackendMembership;
  salon: BackendSalon;
}

/** UI-facing invitation states derived from the backend response. */
export type InvitationState =
  | "missing_token"
  | "login_required"
  | "checking"
  | "accepting"
  | "success"
  | "invalid"
  | "expired"
  | "revoked"
  | "already_accepted"
  | "already_member"
  | "email_mismatch"
  | "error";
