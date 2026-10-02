# P3-D Booking Calendar & Appointment Frontend — Codex

**Status:** Implementation complete; awaiting trusted host verification and auditor review.

## Scope

Implements the P3-D salon appointment calendar only. The page is available at `/salon/appointments` and resolves salon context from the signed-in user's backend memberships. It supports daily date navigation, status filtering, appointment creation, rescheduling, and scheduled/confirmed status actions (confirm, complete, cancel, no-show). Appointment duration, service name, price, and currency are rendered from backend snapshots. Price remains a decimal string.

## Integration and Security

- Added the appointment list/create BFF endpoint, detail/reschedule endpoint, and nested lifecycle action endpoint using existing `authorizedCall` and `applySessionOutcome` session handling.
- List query parameters are allowlisted. Browser JSON never receives token material; salon and appointment IDs are path parameters and backend tenant/RBAC checks remain authoritative.
- Backend conflict and validation response status mapping is retained through the existing safe UI error mapping. The UI surfaces conflict feedback and never makes availability or overlap decisions client-side.
- Booking picker options come from existing customer, active-service and bookable-staff endpoints. Backend remains authoritative for assignment, availability, and eligibility.

## Verification

- TypeScript: **PASS** (`cd apps/web && npx tsc --noEmit`).
- Full frontend Vitest: **PASS**, 29 files / 198 tests.
- ESLint: **PASS** (`npm run lint:web`).
- Default Turbopack production build: blocked in this restricted environment while resolving `next/font` resources.
- Webpack production build attempt: blocked because Next.js could not parse TypeScript `--showConfig`; direct `npx tsc --showConfig -p apps/web/tsconfig.json` also did not return in this environment. Trusted host should run the production build gate.

## Worktree Notes

- Preserved pre-existing unstaged changes in `apps/web/src/lib/auth/backend.ts` and `apps/web/src/lib/auth/contracts.ts`; these define the appointment transport types/wrappers used by this implementation.
- No commit or push performed, per the controlled handoff rule: the frontend worker host owns commit/push and READY_FOR_AUDIT publication after its authoritative gates.
- No merge or deployment performed.
