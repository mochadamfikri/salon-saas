# P2-B Service Catalog Frontend — Codex

**Status:** Implementation and local verification complete; awaiting remote branch publication and auditor review.

## Revision References

- Starting frontend SHA: `2a97a242eebaa4e607f06137fe03d2c98f499e11`
- Final implementation SHA: `7b69f45a70fa3b58363697670948fd43ff758920`
- Authoritative backend SHA: `96b289297bc7f5a0322a0467fb0d962bc2cb7e58`
- Branch: `feature/phase-2-web-codex`

## Scope Inventory

All changes inherited at the starting SHA were baseline Muse work. The earlier attempted dashboard shell, package-tier navigation, platform routes, and dashboard placeholders were off-scope; those files and tracked edits were removed/restored before implementing this service catalog. No booking or salon-management workflow was implemented.

The root `package-lock.json` was out of sync with the existing workspace manifests: `npm ci` rejected it for missing workspace dependency entries. It was regenerated with `npm install --package-lock-only` and clean installation then succeeded. This change does not add application dependencies.

## Implementation

- `apps/web/src/app/salon/services/page.tsx`: authenticated catalog page; salon and role are selected from backend `GET /me/salons` membership data.
- `apps/web/src/components/salon/ServiceCatalog.tsx`: responsive list and create/edit/activate/deactivate UI; active state, category, optional description, duration, exact decimal string price, and currency.
- `apps/web/src/app/api/salons/[salonId]/services/route.ts`: BFF list/create handlers.
- `apps/web/src/app/api/salons/[salonId]/services/[serviceId]/route.ts`: BFF get/edit handlers.
- `apps/web/src/app/api/salons/[salonId]/services/[serviceId]/activate/route.ts` and `.../deactivate/route.ts`: BFF status handlers.
- `apps/web/src/lib/auth/contracts.ts` and `backend.ts`: typed service response/request contracts and backend endpoint wrappers.
- `apps/web/src/lib/service-catalog.ts`: input validation, exact decimal-string validation, payload construction, and PATCH semantics.
- `package-lock.json`: synchronized with declared workspace manifests for reproducible `npm ci`.

## Contract and Security

- Uses only the supplied P2-B endpoints; no DELETE operation is present.
- Browser calls the Next.js BFF only. BFF uses Phase 1 `authorizedCall`/`applySessionOutcome`; token pairs remain HttpOnly cookies and are never returned in JSON.
- The salon ID is selected from authenticated backend memberships in the page. API salon ID comes from the URL route parameter, never from form JSON; backend tenant context/RBAC remains authoritative.
- Owner and Manager see mutation controls. Staff see list/status only. Backend remains responsible for authorization.
- `description` and `category` omissions remain omitted; explicit null is preserved by PATCH to clear values. The edit UI exposes explicit “kirim null” clear checkboxes. Required fields with explicit null are rejected as 422.
- `duration_minutes` must be a positive integer. Price stays a decimal string through form, validation, BFF and backend wrapper; no floating-point arithmetic is used. Numeric(12,2) maximum `9999999999.99` is accepted; larger values are rejected. Currency defaults to IDR in the form, with backend default retained if omitted.
- 401 follows existing auth/session handling; 403, 404 and 422 retain their status mapping; backend details are replaced by safe user messages.

## Verification

- Full Vitest: **PASS**, 24 test files, 177 tests.
- TypeScript (`tsc --noEmit`): **PASS** with Node 24.
- ESLint: **PASS**, no warnings or errors after cleanup.
- `npm ci`: **PASS** after lockfile sync; install environment reports Node 20/npm 10 engine warnings, so validation used Node 24 where needed.
- Production build: **PASS** with `next build --webpack` on Node 24. Default Next.js Turbopack build is separately blocked by this environment: CSS processing attempts subprocess creation/port binding and returns `Operation not permitted (os error 1)`; the same source compiles and completes via the supported Webpack build path.

## Tests Added

- Service input validation: duration, maximum decimal string, exact string transport, currency default, omitted-vs-null semantics.
- BFF route tests: list/create, auth requirement, 403/404/422, membership/path salon context instead of a body salon ID, refresh rotation with HttpOnly cookies, token non-exposure, PATCH clear/omitted semantics, activation and deactivation.
- UI tests: active state/price rendering, Owner/Manager mutation affordances, Staff read-only controls, create submission and explicit nullable-field clearing.

## Remaining Blockers

- Default Turbopack build needs a runner that permits subprocess creation and local port binding; Webpack production build passes.
- `git fetch origin feature/phase-2-web-codex` returned `couldn't find remote ref`; the remote branch did not exist at audit time. Push has not yet been completed, so no remote SHA can be reported.
- No merge was performed.
