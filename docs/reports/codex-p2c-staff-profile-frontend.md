# P2-C Staff Profile Frontend — Codex

**Status:** Implementation complete; awaiting trusted-host build verification and auditor review.

Publication could not be completed in this sandbox: the linked worktree's shared Git metadata is under `/home/ubuntu/salon-saas/.git`, outside the writable workspace. `git commit` fails creating the worktree index lock with `Read-only file system`; no commit or push was created.

## Scope
- Added `/salon/staff` with tenant selection from authenticated membership state.
- Owner/Manager can create profiles for active members, edit profiles, toggle `is_bookable`, and assign/unassign services.
- Staff can read profiles and assignments and edit only their own personal fields. Membership ID remains immutable; no profile-delete action exists.
- Added tenant-scoped Next BFF handlers for profiles, members (for profile creation), and assignment listing/mutation. Tokens remain in the existing server-side authorized-call/cookie flow.
- Added typed backend client contracts, BFF tests, role-aware UI tests, and backend-client tests.

## Contract
Uses the inspected FastAPI P2-C paths and fields: profile creation `{membership_id}`, profile PATCH personal fields, `toggle-bookable` `{is_bookable}`, and service assignment POST/DELETE paths. Backend error statuses are passed through existing safe BFF error mapping; generic backend 409 responses retain HTTP 409. UI distinguishes 404, 409, and 422. Salon IDs come from route context; ownership/RBAC remain backend-authoritative.

## Validation
- Full Vitest: PASS, 26 files / 184 tests.
- TypeScript (`tsc --noEmit`): PASS.
- ESLint: PASS.
- Production build: Turbopack is blocked by sandbox process/port restrictions (`Operation not permitted`). Webpack fallback also fails in Next.js while parsing TypeScript's successful `--showConfig` output (`Could not parse output from TypeScript's --showConfig`); trusted-host build verification is required.

## Follow-up
Checkpoint publication and trusted-host verification remain outstanding. No P2-D/P2-E work was added.
