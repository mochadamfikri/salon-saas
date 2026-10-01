# P2-E Customer Records Frontend — Codex

**Status:** Implementation in progress; blocked from `READY_FOR_AUDIT` by validation and publication gates.

## Scope

- Added authenticated salon customer list/create/detail/update UI at `/salon/customers`.
- Added tenant-path-scoped BFF handlers for `GET`/`POST /salons/{salonId}/customers` and `GET`/`PATCH /salons/{salonId}/customers/{customerId}`. No DELETE handler or UI exists.
- Added typed customer response/request contracts and backend client methods.
- Added frontend input normalization: required trimmed name, lowercased/trimmed email, trimmed nullable email/phone/notes, with omitted PATCH properties left omitted. Duplicate contact values are not rejected.
- The UI supports creating walk-in customers with only a full name; blank optional fields are sent as `null` for explicit clearing.

## Security and Contract

- Salon context for the page comes from the authenticated `/me/salons` membership list; API scope comes from the route parameter, never request-body ownership data.
- BFF uses the existing `authorizedCall` and `applySessionOutcome` session path. Tokens remain server-side and are not added to browser JSON.
- Backend remains authoritative for authorization, validation, and tenant isolation.

## Verification

- Customer input unit tests: **PASS**, 3 tests.
- `git diff --check`: **PASS**.
- Focused ESLint on changed P2-E source: **PASS**, after correcting the hook warning.
- Full Vitest: **BLOCKED**; default fork workers and retry with threads both fail to start workers in this environment. The focused customer test runs successfully using a single thread.
- Full ESLint: **BLOCKED** by the pre-existing uncommitted P2-D `StaffAvailability.tsx` `react-hooks/set-state-in-effect` error. The changed P2-E sources lint cleanly.
- TypeScript and production build: **NOT RUN**; the available runtime is Node 20, while the workspace requires Node 24 and the TypeScript executable is not installed in the current dependency tree.

## Publication Status

- No commit or push was made. Existing uncommitted P2-C/P2-D work is present in the assigned worktree and was preserved; the shared backend client/contracts files contain both that pre-existing work and this checkpoint's additions, so committing them would risk including unrelated scope.
- Branch: `feature/phase-2-web-codex`; starting HEAD: `a16323e78da9e839994bc5eb548dd52779505267`.
- No merge or deployment was performed.

## Remaining to Reach `READY_FOR_AUDIT`

- Re-run full regression tests, TypeScript, full lint, and production build on the required Node 24/npm 11 toolchain with Vitest worker support.
- Resolve or isolate the existing P2-D lint failure without weakening its tests or including unrelated scope.
- Separate/coordinate the shared P2-C/P2-D worktree changes, then commit and push the intended frontend checkpoint changes and update this report with final SHAs.
