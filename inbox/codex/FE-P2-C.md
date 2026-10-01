TARGET_AGENT: CODEX
TASK_ID: FE-P2-C
PHASE: 2
CHECKPOINT: P2-C
TYPE: implementation
PRIORITY: 20
BASE_SHA: a16323e78da9e839994bc5eb548dd52779505267
SOURCE_BRANCH: feature/phase-2-web-codex
STATUS: QUEUED

Implement ONLY Phase 2 P2-C:
Staff Profile + Staff-Service Assignment Frontend.

MANDATORY:

- Work only in /home/ubuntu/salon-saas-frontend.
- Do NOT implement P2-D Availability.
- Do NOT implement P2-E Customers.
- Backend remains read-only source of truth.
- Browser -> Next.js BFF -> FastAPI.
- Tokens remain server-side / HttpOnly.

Owner / Manager:
- create same-tenant StaffProfile
- update same-tenant StaffProfile
- control is_bookable
- assign/unassign services

Staff:
- read same-tenant profiles
- edit only own:
  display_name
  phone
  bio
  photo_url
- service assignments read-only

Rules:
- membership_id immutable
- no StaffProfile hard-delete UI
- preserve backend 404 / 409 / 422 semantics
- add P2-C tests
- update docs/reports/codex-p2c-staff-profile-frontend.md

QUALITY GATE HANDOFF:

Run every validation available inside the Codex sandbox.

If full Vitest worker spawning or Next/Turbopack build is blocked ONLY by
sandbox process restrictions, document that limitation and continue.

Trusted Host Verifier will run full:
- Vitest
- TypeScript
- ESLint
- production build

against the pushed SHA outside the sandbox.

Real source/type/lint/test failures must still be fixed.

Finish with:
- one clean P2-C commit
- push to feature/phase-2-web-codex
- clean working tree
