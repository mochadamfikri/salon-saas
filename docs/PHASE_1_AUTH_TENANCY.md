# Phase 1: Authentication & Multi-Tenant Identity System Specification

Status: APPROVED FOR ENGINEERING  
Base Branch: `develop`  
Approved Phase 0 HEAD: `524977d`  
Repository: `mochadamfikri/salon-saas` (Public)

---

## 1. Phase 1 Objective

Phase 1 establishes the foundational identity, authentication, session management, and multi-tenant security boundary for the entire Salon SaaS platform.

Primary outcomes of Phase 1:
1. Global user identity and profile foundation.
2. User registration, credential login, and logout.
3. Secure password hashing with Argon2id.
4. Short-lived JWT access tokens and rotating opaque refresh sessions.
5. Absolute session revocation and refresh token family reuse detection.
6. Salon (tenant) creation and ownership provisioning.
7. Tenant membership architecture with role-based access control (RBAC).
8. Strict multi-tenant isolation and anti-leakage security boundaries.
9. Staff and manager invitation lifecycle.
10. Password reset token issuance and redemption foundation.
11. Server-side frontend authentication and session state integration.
12. Comprehensive security and cross-tenant access regression tests.

Phase 1 **DOES NOT** implement operational salon features such as booking/reservations, services catalogue, retail products, inventory, payments, invoices, staff scheduling, or customer loyalty programs.

---

## 2. Business & Identity Architecture

### Global User Identity (Decoupled from Tenants)
A user is a global platform entity, completely decoupled from any single salon or business tenant.
- A user may own Salon A, manage Salon B, work as staff in Salon C, and browse Salon D as a customer.
- **Architectural Constraint:** The `users` table **MUST NOT** include `salon_id` or any tenant-scoped `role`.
- Storing `salon_id` on the `users` table is an architectural defect that locks a human user into a single tenant.

### Tenant Roles vs Customer
- Tenant roles exist **strictly** within `salon_memberships`.
- Supported tenant roles in Phase 1:
  - `owner`: Full administrative control over the salon and its memberships.
  - `manager`: Administrative control over staff members and salon operational data.
  - `staff`: Operational team member with no membership administration privileges.
- **Customer is NOT a tenant role.** A customer is simply an authenticated global user interacting with public/customer-facing capabilities. Any user can create a salon and become its initial `owner`.

---

## 3. Membership & RBAC Rules

### Owner
- Automatically assigned to the creator of a salon during salon provisioning.
- Can view all salon memberships.
- Can invite `manager` and `staff` members.
- Can promote `staff` to `manager` and demote `manager` to `staff`.
- Can suspend or remove `manager` and `staff` members.
- Phase 1 scope limits: No owner transfer, no multi-owner co-ownership, and no owner self-demotion.

### Manager
- Can view salon memberships.
- Can invite `staff` members.
- Can suspend or remove `staff` members.
- **Restrictions:** Cannot invite managers, promote/demote managers, touch owner memberships, or modify salon ownership.

### Staff
- Possesses tenant context for future operational interactions.
- **Restrictions:** Zero administrative access over salon memberships or salon settings.

---

## 4. Tenant Model (`salons`)

- Primary Key: `id` (UUIDv4)
- Fields:
  - `id`: UUID (Primary Key)
  - `name`: VARCHAR(200), non-null
  - `slug`: VARCHAR(160), non-null, globally unique
  - `status`: VARCHAR(20), check constraint: `onboarding`, `active`, `suspended` (default `onboarding`)
  - `created_by_user_id`: UUID, foreign key referencing `users.id` (RESTRICT)
  - `created_at`: TIMESTAMPTZ (server default `now()`)
  - `updated_at`: TIMESTAMPTZ (server default `now()`)
- Full branding, rich salon profiles, business hours, and multi-branch structures are deferred to Phase 2.

---

## 5. User Model (`users`)

- Primary Key: `id` (UUIDv4)
- Fields:
  - `id`: UUID (Primary Key)
  - `email`: VARCHAR(320), non-null, unique (normalized lower-case)
  - `password_hash`: VARCHAR(512), non-null
  - `is_active`: BOOLEAN, default `true`
  - `is_super_admin`: BOOLEAN, default `false` (no public elevation endpoints)
  - `email_verified_at`: TIMESTAMPTZ, nullable
  - `last_login_at`: TIMESTAMPTZ, nullable
  - `created_at`: TIMESTAMPTZ (server default `now()`)
  - `updated_at`: TIMESTAMPTZ (server default `now()`)
- Business Rule: Email addresses must be trimmed and converted to lowercase prior to persistence and lookup.

---

## 6. Password Security & Hashing

- Algorithm: Argon2id (via `pwdlib[argon2]`).
- Prohibited algorithms: Plain MD5, SHA-256/512, raw bcrypt, custom cryptography.
- Password constraints:
  - Minimum length: 12 characters.
  - Maximum length: 128 characters.
  - Full Unicode support; no arbitrary forced symbol/casing rules that degrade entropy.

---

## 7. Authentication, Sessions & Token Lifecycle

### Dual Token Architecture
Authentication utilizes short-lived JWT access tokens paired with rotating opaque refresh tokens stored securely in the database.

### Access Token (JWT)
- Lifespan: 15 minutes.
- Required Claims:
  - `sub`: User UUID string
  - `sid`: AuthSession UUID string
  - `typ`: `"access"`
  - `iss`, `aud`, `iat`, `exp`, `jti`
- **Security Rule:** Access tokens do **NOT** bake in `salon_id` or tenant `role`. Tenant context is evaluated dynamically against active memberships on each request.

### Refresh Token & Session (`auth_sessions`)
- Raw refresh tokens are cryptographically generated high-entropy strings (e.g. 256-bit random).
- **Security Rule:** Raw refresh tokens are **NEVER** stored in the database. Only their SHA-256 / cryptographic hash (`token_hash`) is persisted.
- Fields:
  - `id`: UUID (Primary Key)
  - `user_id`: UUID, foreign key referencing `users.id` (RESTRICT)
  - `token_hash`: VARCHAR(128), unique
  - `family_id`: UUID, indexed (tracks rotation family)
  - `expires_at`: TIMESTAMPTZ (recommended 30 days)
  - `last_used_at`: TIMESTAMPTZ, nullable
  - `revoked_at`: TIMESTAMPTZ, nullable
  - `replaced_by_session_id`: UUID, foreign key referencing `auth_sessions.id` (RESTRICT)
  - `user_agent`: VARCHAR(512), nullable
- Token Rotation & Reuse Detection:
  - Each refresh yields a newly generated token and marks the previous session replaced.
  - If an already replaced/revoked token hash is presented, the system detects a token theft attempt and revokes the **entire** `family_id`.

---

## 8. Password Reset Foundation (`password_reset_tokens`)

- Fields:
  - `id`: UUID (Primary Key)
  - `user_id`: UUID, foreign key referencing `users.id` (RESTRICT)
  - `token_hash`: VARCHAR(128), unique
  - `created_at`: TIMESTAMPTZ
  - `expires_at`: TIMESTAMPTZ (recommended 1 hour)
  - `used_at`: TIMESTAMPTZ, nullable
- Raw reset tokens are sent via out-of-band communication and only verified against `token_hash`.

---

## 9. Salon Invitations (`salon_invitations`)

- Fields:
  - `id`: UUID (Primary Key)
  - `salon_id`: UUID, foreign key referencing `salons.id` (RESTRICT)
  - `email`: VARCHAR(320), non-null, indexed
  - `role`: VARCHAR(20), check constraint: `manager`, `staff`
  - `token_hash`: VARCHAR(128), unique
  - `invited_by_user_id`: UUID, foreign key referencing `users.id` (RESTRICT)
  - `created_at`: TIMESTAMPTZ
  - `expires_at`: TIMESTAMPTZ (recommended 7 days)
  - `accepted_at`: TIMESTAMPTZ, nullable
  - `revoked_at`: TIMESTAMPTZ, nullable

---

## 10. Multi-Tenant Isolation & Security Guardrails

1. Every tenant-scoped request must validate that the authenticated user possesses an `active` membership in the targeted salon.
2. In tenant routes (`/salons/{salon_id}/...`), access by non-members or suspended members must be rejected with 404 (preferred for enumeration defense) or 403.
3. Database foreign keys strictly use `ondelete="RESTRICT"` to prevent accidental cascading data loss.
4. Synchronous SQLAlchemy 2.0 with Psycopg 3 is maintained as the production-grade driver (ADR-012).

---

## 11. Phase 1 Task Matrix (P1-001 through P1-030)

| Task ID | Description | Checkpoint / Group | Status |
|---|---|---|---|
| **P1-001** | Public repository security pre-flight + docs reconciliation | Checkpoint A | **COMPLETED** |
| **P1-002** | Create Phase 1 branch, progress document, and spec boundary | Checkpoint A | **COMPLETED** |
| **P1-003** | Design and implement Phase 1 ORM models + Alembic migration | Checkpoint A | **COMPLETED** |
| **P1-004** | Centralized DB session dependency & repository foundation | Checkpoint A | **COMPLETED** |
| **P1-005** | Password hashing service (`pwdlib[argon2]`) and validation | Checkpoint B | Pending |
| **P1-006** | JWT access token creation and verification service | Checkpoint B | Pending |
| **P1-007** | Opaque refresh token generation, hashing, and family rotation | Checkpoint B | Pending |
| **P1-008** | Authentication endpoints: Registration (`POST /auth/register`) | Checkpoint B | Pending |
| **P1-009** | Authentication endpoints: Login (`POST /auth/login`) | Checkpoint B | Pending |
| **P1-010** | Authentication endpoints: Refresh (`POST /auth/refresh`) | Checkpoint B | Pending |
| **P1-011** | Authentication endpoints: Logout & session revocation | Checkpoint B | Pending |
| **P1-012** | Current user identity endpoint (`GET /auth/me`) | Checkpoint B | Pending |
| **P1-013** | Authentication middleware and security dependency injection | Checkpoint B | Pending |
| **P1-014** | Salon creation endpoint (`POST /salons`) & auto-owner provisioning | Checkpoint C | Pending |
| **P1-015** | User salons listing endpoint (`GET /salons/my`) | Checkpoint C | Pending |
| **P1-016** | Salon detail and tenant context endpoint (`GET /salons/{salon_id}`) | Checkpoint C | Pending |
| **P1-017** | Tenant isolation and RBAC permission dependencies | Checkpoint C | Pending |
| **P1-018** | Salon members listing endpoint (`GET /salons/{salon_id}/members`) | Checkpoint C | Pending |
| **P1-019** | Member role update endpoint (`PATCH /salons/{salon_id}/members/{id}`) | Checkpoint C | Pending |
| **P1-020** | Member suspension/removal endpoint | Checkpoint C | Pending |
| **P1-021** | Create staff/manager invitation endpoint | Checkpoint D | Pending |
| **P1-022** | List and revoke salon invitations endpoint | Checkpoint D | Pending |
| **P1-023** | Accept invitation endpoint (`POST /invitations/accept`) | Checkpoint D | Pending |
| **P1-024** | Password reset request and token issuance endpoint | Checkpoint D | Pending |
| **P1-025** | Password reset confirmation endpoint | Checkpoint D | Pending |
| **P1-026** | Comprehensive tenant boundary and cross-tenant leak tests | Checkpoint E | Pending |
| **P1-027** | Frontend auth client, cookie handling, and session state | Checkpoint E | Pending |
| **P1-028** | Frontend login/register and tenant switcher UI | Checkpoint E | Pending |
| **P1-029** | Full suite regression, linting, formatting, and CI validation | Checkpoint E | Pending |
| **P1-030** | Phase 1 final engineering audit report and sign-off | Checkpoint E | Pending |

---

## 12. Definition of Done (DoD) for Phase 1

1. All 6 core schema entities migrated and indexed in PostgreSQL.
2. Complete test suite passing: unit tests, database constraints, authentication flows, token rotation, and multi-tenant isolation.
3. Zero hardcoded secrets, connection strings, or credentials in tracked files or Git history.
4. Clean Alembic upgrade from Phase 0 (`20260929_0001` -> `20260929_0002` -> head), clean base-to-head execution, and downgrade safety verified.
5. All code adheres to PEP 8, Ruff (`py313` target), Black, and strict TypeScript compilation.
6. CI pipeline green on GitHub Actions for feature and integration branches.

---

## 13. Out of Scope for Phase 1

- Operational appointments, calendars, bookings, and slots.
- Service categories, treatment lists, retail product catalog.
- Stripe / Midtrans / Xendit payment gateways or invoice generation.
- WhatsApp / Telegram bot integrations or webhook dispatchers.
- Multi-branch salon hierarchy (`branches`).
- Customer loyalty points, membership subscriptions, and POS terminals.
