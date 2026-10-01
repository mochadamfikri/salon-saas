# P2-E Customer Records Frontend — Codex

**Status:** Implementation complete; ready for trusted-host verification.

## Scope

- Added customer list, create, detail/edit and update UI at `/salon/customers`; no delete action exists.
- Owner, Manager and Staff receive the same create/read/update capabilities in the frontend.
- Added tenant-path BFF endpoints for list/create and detail/update, using the established `authorizedCall` session flow. Backend remains authoritative for tenant and role authorization.
- Added typed backend customer contracts and wrappers.

## Contract Handling

- Full name is required and trimmed on create; PATCH validates it only when supplied and rejects null/blank values.
- Email is trimmed/lowercased; email, phone and notes support explicit null/blank clearing.
- PATCH payload handling preserves omitted fields as omitted; no frontend uniqueness checks, deduplication, ownership field, or DELETE operation is present.
- The form supports a name-only walk-in customer. Browser requests go through the Next.js BFF; backend tokens remain server-side.

## Verification

- `npx tsc --noEmit`: PASS.
- Targeted Vitest customer payload tests: PASS (3 tests).
- ESLint on changed frontend files: PASS.
- Full Vitest suite: PASS (29 files, 198 tests).

## Handoff

No backend edits, merge, deployment, or later checkpoint work performed. Trusted frontend worker owns full quality gates, commit, push, and audit readiness.
