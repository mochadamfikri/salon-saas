# P2-C Staff Profile Frontend — Codex

**Status:** Implementation complete; blocked from `READY_FOR_AUDIT` by environment validation failures. Not committed or pushed.

## Scope

- Added authenticated `/salon/staff` page with salon selection based on the authenticated user's memberships.
- Added staff profile list, selection/detail editing, active-membership profile creation, bookability toggle, and service assignment/unassignment controls.
- Added typed backend contracts and wrappers for staff profiles, membership list, and staff-service assignments.
- Added tenant-scoped BFF routes; all browser calls remain same-origin, token pairs remain server-side/HttpOnly, and backend statuses (including 404/409/422) are preserved.
- Owner/Manager can create profiles from active memberships, edit profiles, toggle bookability, and manage assignments. Staff can read profiles and edit only their own personal fields. No profile-delete workflow is present.

## Contract Notes

- Profile create sends only `membership_id`; profile updates send only `display_name`, `phone`, `bio`, and `photo_url` (empty values become explicit `null`).
- Membership ID is never sent during edits. `is_bookable` uses the backend toggle endpoint and Owner/Manager-only UI.
- The members endpoint is Owner/Manager-only; profile list loading tolerates its 403 so Staff can still read profiles and services.
- No booking or availability workflow was added.

## Verification

- TypeScript (`tsc --noEmit`): **PASS**.
- ESLint: **BLOCKED** — fails on an existing unrelated P2-D `StaffAvailability.tsx` hook lint error (`react-hooks/set-state-in-effect`).
- `git diff --check`: **PASS**.
- Full Vitest: **BLOCKED** — Vitest cannot start fork workers in this sandbox.
- Production build: **BLOCKED** — Turbopack's CSS processing requires subprocess creation/port binding, denied by this sandbox (`Operation not permitted`). The available runtime is Node 20; the project declares Node 24.

## Remaining Work

- Rerun full frontend tests and production build on a permitted Node 24 runner with worker/process permissions.
- Resolve the unrelated P2-D lint error in its assigned checkpoint, then rerun ESLint.
- Keep the existing mixed-checkpoint working tree intact; commit and push after the required quality gates pass and checkpoint changes can be isolated safely.
- No merge or deployment was performed.
