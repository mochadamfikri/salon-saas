# Salon SaaS Orchestrator

Control-plane knowledge and policy scaffold for the Salon SaaS engineering workflow.

## Roles
- Owner: business/product authority.
- ChatGPT: Product Architect, Auditor, Orchestrator.
- Hermes: Backend Engineer.
- Codex: Frontend Engineer.
- GitHub: source of truth for code, reports, handoffs, and audit artifacts.
- Worker/systemd layer: persistent process supervisor (to be wired on VPS).

## Core Principle
**AGENT KNOWLEDGE IS REHYDRATED, NOT REMEMBERED.**

Every fresh agent session rebuilds working context from authoritative files instead of relying on old conversation history.

## Required Prompt Assembly Order
### Hermes
1. `policies/PROJECT_RULES.md`
2. `policies/HERMES_RULES.md`
3. `knowledge/PROJECT_MASTER_PLAN.md`
4. `knowledge/PHASE1_BASELINE.md`
5. `knowledge/phases/PHASE2_MASTER_SPEC.md`
6. `knowledge/BUSINESS_DECISIONS.md`
7. current backend handoff
8. active task from `inbox/hermes/`

### Codex
1. `policies/PROJECT_RULES.md`
2. `policies/CODEX_RULES.md`
3. `knowledge/PROJECT_MASTER_PLAN.md`
4. `knowledge/PHASE1_BASELINE.md`
5. `knowledge/phases/PHASE2_MASTER_SPEC.md`
6. `knowledge/BUSINESS_DECISIONS.md`
7. authoritative audited backend contract/report for active checkpoint
8. current frontend handoff
9. active task from `inbox/codex/`

## Queue Convention
- `inbox/hermes/` => backend jobs only.
- `inbox/codex/` => frontend jobs only.
- `audit/hermes/` and `audit/codex/` => audit results.
- `completed/...` => consumed jobs.
- A task identifies target agent, checkpoint, authoritative SHA(s), acceptance criteria, and completion signal.

## Status Vocabulary
- `IN_PROGRESS`
- `READY_FOR_AUDIT`
- `REVISE`
- `BLOCKED`
- `FINAL_PASS`

Only the auditor may issue `FINAL_PASS`.

## Owner Admin Control Panel

The control plane includes a separate mobile-first Owner dashboard specification under:
- `knowledge/ADMIN_CONTROL_PANEL_SPEC.md`
- `policies/ADMIN_PANEL_SECURITY_RULES.md`
- `contracts/CONTROL_PLANE_API.md`
- `contracts/EVENT_SCHEMA.md`
- `runtime/STATE_MODEL.md`
- `notifications/NOTIFICATION_POLICY.md`
- `admin-panel/`

The panel provides real-time worker state, notification bell, queue/task inspection, phase upload/activation, audit visibility, report download, business decisions, and safe read-only logs.

It must never expose arbitrary shell access or routine production deployment controls.
