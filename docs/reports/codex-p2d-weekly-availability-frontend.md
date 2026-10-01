# P2-D Weekly Availability Frontend — Codex

**Status:** Implementation complete; frontend checks pass except production build, blocked by this runner's Next.js TypeScript-config parsing after Turbopack's sandbox process/port restriction. Awaiting trusted-host verification and auditor review.

## Revision References

- Starting frontend SHA: `8eb7936449e2cd1f5f4b0bbcbdb5a7b5dbe1178f`
- Branch: `feature/phase-2-web-codex`
- Backend contract: Phase 2 P2-D completion report; endpoints and role/overlap contract match the audited backend report.

## Implementation

- `apps/web/src/app/salon/availability/page.tsx`: authenticated salon-context availability page.
- `apps/web/src/components/salon/WeeklyAvailability.tsx`: weekly schedule by Monday–Sunday, profile selection, add/edit/delete, own-staff mutation gating, and client validation.
- `apps/web/src/app/api/salons/[salonId]/staff-profiles/[profileId]/availability/route.ts`: tenant-scoped BFF list/create.
- `apps/web/src/app/api/salons/[salonId]/staff-profiles/[profileId]/availability/[availabilityId]/route.ts`: tenant-scoped BFF patch/delete.
- `apps/web/src/lib/auth/contracts.ts` and `backend.ts`: typed availability contract and backend wrappers.

Browser requests use only the Next.js BFF. Backend tokens remain handled by existing `authorizedCall` session infrastructure and are not exposed in JSON. Backend authorization and tenant checks remain authoritative. UI permits Owner/Manager to manage all same-salon profiles and Staff to manage only the profile linked to the authenticated membership. A 409 overlap/conflict receives a clear UI message. Adjacent times remain allowed by strict start-before-end client validation; overlap detection remains backend authoritative.

## Verification

- Focused weekly availability tests: **PASS** as part of the full suite.
- Full Vitest: **PASS**, 28 test files, 195 tests.
- TypeScript (`npx tsc --noEmit`): **PASS**.
- ESLint: **PASS**.
- Default production build: **BLOCKED by sandbox**; Turbopack fails attempting subprocess creation/local port binding (`Operation not permitted`).
- Webpack production build: attempted, but Next reports `Could not parse output from TypeScript's --showConfig`; direct `npx tsc --showConfig` emits valid JSON and TypeScript passes. This is an environment/build-tool issue pending trusted-host verification.

## Tests Added

- Weekly schedule displays fetched slot times.
- Staff can submit a slot for their own membership profile.
- Staff receive read-only controls for another member's profile.
