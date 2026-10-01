# Phase 1 Baseline — Authentication & Tenancy

## Core Identity Model
- `users` is global identity.
- Tenant role does not live on `users`.
- Tenant roles live in salon membership.
- Tenant roles: `owner`, `manager`, `staff`.
- `customer` is not a tenant membership role.

## Security Baseline
- Backend is authoritative for auth/RBAC/tenant isolation.
- Browser does not own backend token pairs.
- Next.js BFF/server boundary protects token handling.
- Refresh rotation/session handling from Phase 1 must be reused, not reinvented.

## Frontend Baseline
Accepted Phase 1 frontend baseline commit:
`2a97a242eebaa4e607f06137fe03d2c98f499e11`

## Compatibility Rule
Phase 2 must not regress authentication, membership/tenant resolution, invitations, token non-exposure, or BFF session refresh semantics.

## Remaining Acceptance Note
Project history still tracks final Phase 1 integration/checkpoint-E closure separately. Do not silently claim it completed without explicit audit.
