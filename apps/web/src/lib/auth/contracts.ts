/**
 * Typed contracts for the Salon SaaS FastAPI backend (Phase 1).
 *
 * These mirror the backend Pydantic schemas on branch
 * `feature/phase-1-auth-tenancy`. The backend is the source of truth;
 * the frontend must never invent fields the backend does not return.
 *
 * Invitation contracts are marked EXPECTED: the backend implements them in
 * Checkpoint D (P1-021..P1-023), which is not merged yet. The frontend
 * implements against the approved contract from docs/PHASE_1_AUTH_TENANCY.md
 * and documents the expectation here.
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

/** POST /salons request. Slug is required by the backend contract. */
export interface BackendSalonCreateRequest {
  name: string;
  slug: string;
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
 * EXPECTED backend contract (Checkpoint D, P1-023 — not implemented yet).
 *
 * Approved endpoint: POST /invitations/accept
 * Approved request:  { "token": "<raw invitation token>" }
 *
 * Expected success (200): the created membership plus salon context.
 * Expected failures (mapped by backend `detail` string):
 *  - 404 "Invitation not found"        -> invalid token
 *  - 410 "Invitation expired"          -> expired
 *  - 410 "Invitation revoked"          -> revoked
 *  - 409 "Invitation already accepted" -> already accepted
 *  - 422 "Email mismatch"              -> invitation email != user email
 *  - 401                               -> not authenticated
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
  | "email_mismatch"
  | "error";
