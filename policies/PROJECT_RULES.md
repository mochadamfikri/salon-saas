# Salon SaaS — Global Engineering Rules

## Authority
- **Owner** owns business requirements, product scope, production approval, and unresolved business decisions.
- **ChatGPT** acts as Product Architect, Auditor, and Orchestrator; it may issue PASS/REVISE/BLOCKED audit outcomes.
- **Hermes** is Backend Engineer.
- **Codex** is Frontend Engineer.
- Agents must not invent new business rules.

## Source of Truth
Priority:
1. current repository source and migrations;
2. explicit Owner decisions;
3. audited contracts/reports;
4. current phase master spec;
5. persistent handoff;
6. active task.

Conversation history is disposable context, not permanent project state.

## Multi-Tenancy
Salon SaaS is multi-tenant.
- Backend tenant context is authoritative.
- Never trust tenant/resource ownership from client payload when server-side context exists.
- Prevent cross-salon reads and mutations.
- Cross-tenant resources use 404 where the approved contract specifies it.
- Frontend role visibility is UX only; backend authorization remains authoritative.

## Security
Never:
- expose access/refresh tokens to browser JSON;
- commit secrets, passwords, API keys, or production credentials;
- log secret material;
- bypass auth/RBAC/tenant checks for convenience;
- test destructive behavior against production.

Browser → Next.js/BFF → FastAPI remains the approved boundary.

## Scope Discipline
Work only on the active checkpoint.
Do not implement unrelated dashboard, booking, POS, payments, payroll, attendance, inventory, analytics, marketing, package tiers, or later-phase work unless explicitly assigned.
Scope creep is an audit failure.

## Git and Deployment
Agents may work only on their assigned worktree/branch.
Never without explicit Owner approval:
- merge to `develop` or `main`;
- force-push;
- deploy/restart production;
- modify production secrets;
- perform destructive production DB operations.

Commit focused logical changes. Reports may be separate commits.

## Validation and Errors
- Validate server-side; client validation is UX only.
- Expected domain/client failures must be deterministic and not leak as HTTP 500.
- Relevant DB race/unique violations may map to deterministic domain errors after rollback.
- Do not disguise unrelated `IntegrityError` as a business conflict.

## Tests
Never delete, skip, or weaken tests just to get green.
When tests fail: diagnose root cause → fix → rerun.
Regression suite is mandatory before `READY_FOR_AUDIT`.

## Completion
A checkpoint reaches `READY_FOR_AUDIT` only when:
- implementation complete;
- required tests pass;
- relevant lint/type/format/build gates pass;
- commit(s) pushed;
- report written;
- handoff updated;
- working tree clean.

Only the auditor can declare `FINAL_PASS`.

## Context Management
Agent sessions are disposable.
At startup:
- verify worktree;
- verify branch;
- inspect HEAD/status/diff;
- read policies/spec/handoff/task.

Before context exhaustion:
- persist state in Git/handoff;
- preserve WIP;
- do not `reset --hard`;
- rotate to a fresh session.
