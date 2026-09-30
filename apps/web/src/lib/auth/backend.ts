/**
 * Server-side typed client for the Salon SaaS FastAPI backend.
 *
 * Pure module: no Next.js imports, so it is fully unit-testable with an
 * injected fetch implementation. All methods return a discriminated
 * `BackendResult` — never throw for expected HTTP error statuses.
 */

import type {
  BackendInvitationAcceptRequest,
  BackendInvitationAcceptResponse,
  BackendLoginRequest,
  BackendMySalon,
  BackendRefreshRequest,
  BackendRegisterRequest,
  BackendSalon,
  BackendSalonCreateRequest,
  BackendTokenPair,
  BackendUser,
} from "./contracts";

/** Machine-readable error codes derived from backend responses. */
export type BackendErrorCode =
  | "invalid_credentials"
  | "account_inactive"
  | "email_taken"
  | "invalid_refresh_token"
  | "slug_taken"
  | "salon_not_found"
  | "invitation_invalid"
  | "invitation_expired"
  | "invitation_revoked"
  | "invitation_already_accepted"
  | "invitation_duplicate_membership"
  | "invitation_email_mismatch"
  | "invitation_unavailable"
  | "validation_error"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "rate_limited"
  | "network_error"
  | "unknown_error";

export type BackendResult<T> =
  | { ok: true; data: T; status: number }
  | {
      ok: false;
      code: BackendErrorCode;
      status: number;
      detail: string;
      /** Seconds from the backend's `Retry-After` header (429 only). */
      retryAfterSeconds?: number;
    };

export type FetchImpl = typeof fetch;

export interface BackendClientOptions {
  baseUrl: string;
  fetchImpl?: FetchImpl;
  timeoutMs?: number;
}

/**
 * Map a backend error response to a stable, UI-safe error code.
 * Backend `detail` strings are matched defensively (case-insensitive,
 * substring) because exact wording is backend-owned and may evolve.
 */
export function mapBackendError(status: number, detail: string): BackendErrorCode {
  const d = detail.toLowerCase();

  if (status === 401) {
    if (d.includes("email") && d.includes("password")) return "invalid_credentials";
    if (d.includes("refresh")) return "invalid_refresh_token";
    return "unauthorized";
  }
  if (status === 403) {
    if (d.includes("not active")) return "account_inactive";
    return "forbidden";
  }
  if (status === 404) {
    if (d.includes("invitation")) return "invitation_invalid";
    if (d.includes("salon")) return "salon_not_found";
    return "not_found";
  }
  if (status === 409) {
    // Backend wordings: "Invitation has already been accepted" and
    // "User already has an active membership in this salon".
    if (d.includes("already") && d.includes("accept")) return "invitation_already_accepted";
    if (d.includes("already") && d.includes("membership"))
      return "invitation_duplicate_membership";
    return "unknown_error";
  }
  if (status === 410) {
    if (d.includes("expir")) return "invitation_expired";
    if (d.includes("revok")) return "invitation_revoked";
    return "unknown_error";
  }
  if (status === 422) {
    if (d.includes("email") && d.includes("mismatch")) return "invitation_email_mismatch";
    if (d.includes("already registered") || d.includes("already exists")) {
      return d.includes("slug") ? "slug_taken" : "email_taken";
    }
    return "validation_error";
  }
  if (status === 429) return "rate_limited";

  // Some backends use 400 with a descriptive detail for duplicates.
  if (status === 400) {
    if (d.includes("email") && d.includes("register")) return "email_taken";
    if (d.includes("slug")) return "slug_taken";
    return "validation_error";
  }

  return "unknown_error";
}

function safeDetail(value: unknown): string {
  if (typeof value === "string") return value.slice(0, 300);
  if (value && typeof value === "object" && "detail" in value) {
    const d = (value as { detail: unknown }).detail;
    if (typeof d === "string") return d.slice(0, 300);
  }
  return "Unexpected backend response";
}

/**
 * Parse the backend's `Retry-After` response header (seconds) into a
 * positive integer, or undefined when absent/invalid. The backend sends it
 * on 429 responses with the rate-limit window length.
 */
function parseRetryAfter(value: string | null): number | undefined {
  if (value === null) return undefined;
  const seconds = Number.parseInt(value.trim(), 10);
  if (!Number.isFinite(seconds) || seconds <= 0) return undefined;
  return Math.min(seconds, 3600);
}

export class BackendClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchImpl;
  private readonly timeoutMs: number;

  constructor(options: BackendClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 10_000;
  }

  private async request<T>(
    path: string,
    init: { method: string; body?: unknown; accessToken?: string },
  ): Promise<BackendResult<T>> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const headers: Record<string, string> = { "content-type": "application/json" };
      if (init.accessToken) headers["authorization"] = `Bearer ${init.accessToken}`;

      let response: Response;
      try {
        response = await this.fetchImpl(`${this.baseUrl}${path}`, {
          method: init.method,
          headers,
          body: init.body === undefined ? undefined : JSON.stringify(init.body),
          signal: controller.signal,
        });
      } catch {
        return { ok: false, code: "network_error", status: 0, detail: "Backend unreachable" };
      }

      let payload: unknown = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }

      if (response.ok) {
        return { ok: true, data: payload as T, status: response.status };
      }

      const detail = safeDetail(payload);
      const retryAfterSeconds = parseRetryAfter(response.headers.get("retry-after"));
      return {
        ok: false,
        code: mapBackendError(response.status, detail),
        status: response.status,
        detail,
        ...(retryAfterSeconds !== undefined ? { retryAfterSeconds } : {}),
      };
    } finally {
      clearTimeout(timer);
    }
  }

  register(body: BackendRegisterRequest): Promise<BackendResult<BackendTokenPair>> {
    return this.request<BackendTokenPair>("/auth/register", { method: "POST", body });
  }

  login(body: BackendLoginRequest): Promise<BackendResult<BackendTokenPair>> {
    return this.request<BackendTokenPair>("/auth/login", { method: "POST", body });
  }

  refresh(body: BackendRefreshRequest): Promise<BackendResult<BackendTokenPair>> {
    return this.request<BackendTokenPair>("/auth/refresh", { method: "POST", body });
  }

  getMe(accessToken: string): Promise<BackendResult<BackendUser>> {
    return this.request<BackendUser>("/auth/me", { method: "GET", accessToken });
  }

  /** Best-effort: revokes the session bound to the access token. */
  logout(accessToken: string): Promise<BackendResult<{ message: string }>> {
    return this.request<{ message: string }>("/auth/logout", { method: "POST", accessToken });
  }

  createSalon(accessToken: string, body: BackendSalonCreateRequest): Promise<BackendResult<BackendSalon>> {
    return this.request<BackendSalon>("/salons", { method: "POST", body, accessToken });
  }

  getMySalons(accessToken: string): Promise<BackendResult<BackendMySalon[]>> {
    return this.request<BackendMySalon[]>("/me/salons", { method: "GET", accessToken });
  }

  /**
   * POST /invitations/accept — canonical Phase 1 contract (backend
   * Checkpoint D, live on `feature/phase-1-auth-tenancy`).
   *
   * Success (200): { membership, salon }. Failures: 401 unauthenticated,
   * 404 invalid token, 409 already accepted / duplicate membership, 410
   * expired or revoked, 422 email mismatch, 429 rate limited (with a
   * `Retry-After` header in seconds).
   *
   * Defensive fallback: a 404 whose detail is exactly FastAPI's default
   * `{"detail": "Not Found"}` means the route itself is missing (backend
   * older than Checkpoint D); it maps to `invitation_unavailable` so the
   * UI can explain invitations are not enabled instead of failing
   * cryptically. A 404 whose detail mentions the invitation is a genuinely
   * invalid token.
   */
  async acceptInvitation(
    accessToken: string,
    body: BackendInvitationAcceptRequest,
  ): Promise<BackendResult<BackendInvitationAcceptResponse>> {
    const result = await this.request<BackendInvitationAcceptResponse>("/invitations/accept", {
      method: "POST",
      body,
      accessToken,
    });
    if (!result.ok && result.status === 404 && result.detail === "Not Found") {
      return { ...result, code: "invitation_unavailable" };
    }
    return result;
  }
}
