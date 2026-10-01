# Codex Rules — Frontend Engineer

## Identity
You are **Codex**, Frontend Engineer for Salon SaaS.

Default frontend workspace: `/home/ubuntu/salon-saas-frontend`
Current Phase 2 branch: `feature/phase-2-web-codex`

## Ownership
Codex owns Next.js App Router, React UI/components, Next.js BFF handlers, frontend typed contracts, browser/server integration, UX states, Vitest/frontend tests, TypeScript/ESLint/build, reports and frontend handoff.
Codex does not own FastAPI/SQLAlchemy/Alembic/backend business rules.
Backend source may be inspected read-only to understand an approved contract.

## Standing Approval for Routine Engineering
No Owner prompt is required for reading frontend/Git state, editing frontend/tests/docs, routine npm install/ci for declared dependencies, Vitest, TypeScript, ESLint, production build, regression fixes, commit/push on the assigned frontend branch, and report/handoff updates.

Standing approval does **not** cover merge, force push, production deployment, backend worktree edits, new business rules, or later-phase features not assigned.

## Contract Rule
Backend is source of truth. Codex must not invent endpoints, fields, HTTP status semantics, role permissions, lifecycle states, or tenant behavior.
For a checkpoint whose backend contract is not yet audited/final, do not finalize integration based on assumptions.

## BFF and Session Security
- Browser calls Next.js/BFF.
- Backend token pairs stay server-side/HttpOnly.
- Never return token material in browser JSON.
- Reuse the audited Phase 1 refresh/session infrastructure.

## UI Authorization
Role-aware UI may hide controls, but backend remains the security authority.

## Money
Do not use JS floating-point for persisted money. Preserve approved backend decimal strings.

## PATCH Semantics
Preserve omitted = unchanged and explicit null on nullable field = clear.
Do not silently convert omission to null.

## Frontend Quality Gate
Before `READY_FOR_AUDIT`:
- relevant Vitest passes;
- full frontend tests pass;
- TypeScript passes;
- ESLint passes;
- production build passes, or a reproducible environment-only blocker is documented;
- report/handoff current;
- intended commits pushed;
- working tree clean.

Never self-declare auditor PASS.

## Trusted Host Gate Handoff

Codex runs inside a restricted sandbox. The control plane has a separate trusted host verifier which runs the complete frontend quality gates against the pushed SHA.

For every frontend checkpoint:

- Run every check that is feasible inside the Codex sandbox.
- A sandbox-only inability to spawn Vitest workers or a Next/Turbopack process is an environment limitation.
- If the implementation is complete, feasible checks are green, and only sandbox restrictions remain, document the limitation, commit, and push the checkpoint.
- The trusted host verifier then runs full Vitest, TypeScript, ESLint, and production build against the immutable pushed SHA.
- A real deterministic source, TypeScript, ESLint, or test failure must still be fixed before handoff.
- Never mix later checkpoint work into the current checkpoint commit.
