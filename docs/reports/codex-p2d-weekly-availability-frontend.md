# P2-D Weekly Availability Frontend — Codex

**Status:** Implementation drafted; blocked before READY_FOR_AUDIT by unavailable validation dependencies/environment.

## Scope

- Added a weekly availability page and profile-scoped slot list/create/edit/delete UI.
- Added typed FastAPI client methods and tenant-scoped BFF handlers for availability list/create/update/delete.
- UI limits Staff to their own profile based on authenticated membership ID; Owner/Manager can select same-salon profiles. Backend remains authoritative for RBAC and tenant isolation.
- Validates weekday and start/end values in the BFF and UI. HTTP 409 is rendered as an overlap conflict; adjacent ranges are not rejected by frontend overlap logic.
- No booking or appointment functionality was added.

## Verification

- TypeScript: **PASS** (`./apps/web/node_modules/.bin/tsc --noEmit -p apps/web/tsconfig.json`).
- `git diff --check`: **PASS**.
- Full Vitest: **BLOCKED**; `npm run test:web` could not start fork workers. The workspace-local Vitest executable is absent, preventing a single-thread retry.
- ESLint: **BLOCKED**; workspace ESLint reports no `eslint.config.*` file. The registry is unreachable (`EAI_AGAIN`), so missing packages/configuration cannot be repaired in this environment.
- Production build: **BLOCKED**; workspace Next executable is missing and npm cannot reach the registry to install declared dependencies.

## Remaining Work

- Restore/install the declared frontend dependencies and ensure the expected lint configuration is present, then run full frontend tests, ESLint, and production build.
- Add focused availability BFF/UI regression tests and rerun the full suite.
- Commit and push the assigned frontend branch after all gates pass.

## Worktree Note

Existing uncommitted P2-C files were present at task start and have been preserved. No commit or push was made because P2-D validation did not pass and the pre-existing P2-C WIP is mixed into the worktree.
