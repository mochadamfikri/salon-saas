# Phase 1 Web Integration Readiness Report

**Date:** 2026-09-30
**Branch:** `feature/phase-1-web-auth-muse` (frontend, Muse.ai)
**Backend contract baseline:** `origin/feature/phase-1-auth-tenancy` @ `5171a18` (Checkpoint D FINAL PASS)
**Audit:** Targeted Contract Compatibility Audit (Auditor work order, 2026-09-30)

This report certifies the frontend's integration readiness against the live
backend contract after the audit. Every item below was verified against the
backend source at the pinned commit — not against the Checkpoint D prose plan.

---

## 1. Endpoint-by-endpoint contract verification

### 1.1 Register — `POST /auth/register` (backend) ← `POST /api/auth/register` (BFF) ← `/register` (page)

| | Backend | BFF | UI |
|---|---|---|---|
| Request | `{ email, password }` | same | LoginForm/RegisterForm validate client-side first (`validateEmail`, `validatePassword`) |
| Success | 201 `{ access_token, refresh_token, token_type: "bearer" }` | 201 `{ ok: true, user }`; tokens set as HttpOnly cookies (`at`/`rt`) | Redirects to `/dashboard` |
| Email taken | 400 "Email already registered" | 400, code `email_taken` | "An account with this email already exists. Try signing in instead." |
| Validation | 422 Pydantic | 422, code `validation_error` | Field-level message |
| Rate limit | 429 + `Retry-After` (5 req/60s/IP) | 429, code `rate_limited` | `errorMessageFor` uses the `Retry-After` seconds when present: "Too many attempts. Please try again in N seconds." |

Cookie lifetimes match the backend exactly: access 15 min, refresh 30 days.

### 1.2 Login — `POST /auth/login` (backend) ← `POST /api/auth/login` (BFF) ← `/login` (page)

| | Backend | BFF | UI |
|---|---|---|---|
| Request | `{ email, password }` (OAuth2PasswordRequestForm) | same | Same validation as register |
| Success | 200 `{ access_token, refresh_token }` | 200 `{ ok: true, user }` + cookies | Redirects to `/dashboard` |
| Bad creds | 401 "Invalid email or password" | 401, code `invalid_credentials` | **Generic message, no user-enumeration oracle:** "Invalid email or password." |
| Inactive account | 403 "Account is not active" | 403, code `account_inactive` | "Your account is not active. Please contact support." |
| Rate limit | 429 + `Retry-After` (10 req/60s/IP) | 429 + hint | Same Retry-After-aware message as register |

No token material ever reaches the browser: `bffErrorResponse` payloads
asserted to carry no `access_token` / `refresh_token` / `token` fields (test).

### 1.3 Session — `GET /auth/me` (backend) ← `GET /api/auth/me` (BFF)

`authorizedCall` (single attempt, no refresh loop) → `backend.getMe`.
On `sessionInvalidated`, `applySessionOutcome` clears both cookies; otherwise
cookies are untouched.

### 1.4 Refresh — `POST /auth/refresh` (backend) ← `POST /api/auth/refresh` (BFF)

- Backend rotates the token pair; reuse of an old token revokes the entire
  family (401) — the BFF treats this as session-dead and clears cookies.
- **Audit fix:** a 429 from the backend refresh endpoint is no longer treated
  as session failure. It returns 429 with the `Retry-After` hint and the
  cookies are left alone. (Previously the BFF cleared cookies on *every*
  refresh failure, logging the user out on a mere rate limit.)
- The inline-refresh path (`authorizedCallWithTokens`) behaves identically:
  429 → `rate_limited` + `retryAfterSeconds`, no `sessionInvalidated`.

### 1.5 Salons — `GET /my-salons`, `POST /salons` (backend) ← `/api/salons` (BFF) ← `/onboarding` (page)

- `GET /my-salons` → list; `POST /salons { name, slug? }` → 201
  `SalonResponse{ id, name, slug, status }` (status: `onboarding|active|suspended`).
- Slug conflict: 400 "Slug already taken" → BFF code `slug_taken` → field
  message on the onboarding form.

### 1.6 Invitation accept — `POST /invitations/accept` (backend) ← `POST /api/invitations/accept` (BFF) ← `/invite/[token]` (page)

The canonical contract (backend Checkpoint D, live):

| Backend | BFF code | HTTP | UI state / message |
|---|---|---|---|
| 200 `{ membership, salon }` | — | 200 | `success` — salon name + role card |
| 401 | `unauthorized` | 401 | `login_required` — invite continuation: raw token parked server-side under a random nonce; user is sent to login and the accept resumes after auth |
| 404 "Invalid invitation token" | `invitation_invalid` | 404 | `invalid` |
| 409 "Invitation has already been accepted" | `invitation_already_accepted` | 409 | `already_accepted` — "This invitation was already accepted." + dashboard link |
| 409 "User already has an active membership in this salon" | `invitation_duplicate_membership` ← **audit fix** | 409 | `already_member` ← **audit fix** — "You are already a member of this salon. No need to accept again." + dashboard link |
| 410 "Invitation has expired" | `invitation_expired` | 410 | `expired` |
| 410 "Invitation has been revoked" | `invitation_revoked` | 410 | `revoked` |
| 422 "Invitation email mismatch:..." | `invitation_email_mismatch` | 422 | `email_mismatch` — asks the user to sign in with the invited email |
| 429 + `Retry-After` (20 req/60s/IP) | `rate_limited` | 429 | Retry-After-aware message; session NOT cleared |

Two real bugs found and fixed by the audit tests (they were invisible before
because the tests used the old guessed wordings):
1. `invitation_duplicate_membership` was entirely unmapped (both 409s collapsed
   to the first branch or `unknown_error`).
2. `invitation_already_accepted` never matched the real backend wording
   ("Invitation **has already been** accepted" — no substring "already accepted"),
   so it silently returned `unknown_error`. Fixed by matching
   `includes("already") && includes("accept")` with the duplicate-membership
   branch checked on `includes("membership")`.

### 1.7 Password reset — `POST /auth/password-reset/request|confirm` (backend)

Backend-only foundation in Phase 1 (P1-024/P1-025). **No UI was built**
(deliberate scope decision, see §4). The frontend contains zero references to
password reset.

### 1.8 Invitation management (create / list / revoke)

Backend has `POST /invitations` (owner-only), `GET /invitations`,
`DELETE /invitations/{id}`. **No management UI was built** — only the accept
flow, consistent with Phase 1 scope.

---

## 2. Cookie behavior

- Session cookies `at` / `rt`: HttpOnly, SameSite=Lax, Secure in production,
  Path=/, no JS access, nothing in localStorage (verified by scan).
- Lifetimes: access 15 min / refresh 30 days — identical to backend config.
- Cleared on: explicit logout, dead refresh (401, reuse detection),
  `sessionInvalidated` from any authorized call.
- **Not** cleared on: 429 (audit fix), network errors, or any non-session
  backend error.

## 3. Protecting tests (153 tests / 18 files, all passing)

Audit-added regression coverage:
- `backend.test.ts` — 409 duplicate-membership mapping; 409 already-accepted
  with the *real* backend wording; `Retry-After` capture (valid seconds,
  missing/invalid/negative/zero header → `undefined`).
- `bff.test.ts` — 429 during refresh returns `rate_limited` + `retryAfterSeconds`
  with **no** `sessionInvalidated`; `bffErrorResponse("invitation_duplicate_membership")` → 409.
- `ui-messages.test.ts` — `rateLimitedMessage` seconds/minutes/fallback;
  `errorMessageFor` honors Retry-After only for `rate_limited`; new
  code/state/message registered.
- `invitations.test.ts` — 429 accept → 429 status, "N seconds" message,
  session kept; 429 during inline refresh → same; duplicate-membership case in
  the state table.
- `accept/route.test.ts` — 409 duplicate → `already_member` state via HTTP.

Full verification: vitest 153/153, `tsc --noEmit`, ESLint, production build —
all green (2026-09-30).

## 4. Known gaps and integration caveats

1. **Password reset UI does not exist.** The backend endpoints are
   foundation-only: with no email provider wired, the reset token is only
   recoverable from the database, so the flow cannot work end-to-end. Building
   UI now would be scope creep. Scheduled for Checkpoint E / Phase 2.
2. **Invitation management UI does not exist** (create/list/revoke). Accept-only
   is in Phase 1 scope.
3. **Invite continuation is best-effort server-side.** The raw token is parked
   under a random nonce in server memory (not a cookie/store); a server restart
   between "continue" and login drops the pending invitation and the user must
   re-open the invite link.
4. **429 UX is honest but dumb.** We surface the backend's Retry-After wait in
   the message; there is no client-side countdown or auto-retry.
5. Backend rate limits are per-IP (60s windows: register 5, login 10,
   refresh 60, password_reset 5, invitation_accept 20). Users behind shared
   NAT may see 429s from other users' traffic — the new messages explain this
   as "too many attempts".
6. The 84 DB-backed backend tests could not run in this sandbox (no
   Postgres/Redis/.env); Hermes must run the full backend suite before the
   Auditor's sign-off, same as the Checkpoint D remediation.

---

*Prepared by Muse.ai (frontend) for the Auditor's Targeted Contract
Compatibility Audit. All fixes are frontend-only; no backend files touched.*
