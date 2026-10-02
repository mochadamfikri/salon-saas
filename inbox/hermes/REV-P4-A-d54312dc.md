TARGET_AGENT: HERMES
TASK_ID: REV-P4-A-d54312dc
PHASE: 4
CHECKPOINT: P4-A
TYPE: revision
PRIORITY: 5
AUTHORITATIVE_SHA: d54312dccb26f07614a2fe286a76ec9c27c7efa8
AUDIT_BASE_SHA: 58dd0a8c70798add0299288031c035873763650e
SOURCE_AUDIT_TASK: AUDIT-P4-A
AUDIT_REPORT: /home/ubuntu/salon-orchestrator/audit/hermes/AUDIT-P4-A-d54312dc.md
STATUS: COMPLETED

Fix every blocking finding in the audit report below. Work on the current engineering branch, preserve later compatible work, run the required regression/quality gates, commit, push, update the completion/handoff report, then stop READY_FOR_AUDIT. Do not merge, deploy, change production, or invent business rules.

===== AUDIT REPORT =====
**Audit Report**
- Checkpoint: P4-A
- Audited SHA: `d54312dccb26f07614a2fe286a76ec9c27c7efa8`
- Scope: Branch CRUD, tenant scoping, role checks, schema validation, migration, and branch tests.
- Verification: Trusted-host verifier reports 337 tests, Ruff check/format, and Black all PASS. Local targeted `pytest tests/test_branch.py` could not run because `pytest` is unavailable in this shell.
- Finding — **High**: `apps/api/app/routers/branch.py:56` maps every `IntegrityError` during branch creation to “Branch code already exists” (409). The project rules require unrelated integrity failures not be disguised as business conflicts; restrict this mapping to the salon/code uniqueness violation and propagate or handle other failures appropriately.
- Residual notes: Tenant-context scoping, Owner/Manager mutation authorization, 404 handling for cross-tenant branch reads, timezone validation, and the `Asia/Jakarta` default-branch migration were inspected. Worktree is clean.
- Verdict rationale: The broad integrity-error mapping violates the approved deterministic error-handling rule; this needs correction before pass.

AUDIT_VERDICT: REVISE
AUDITED_SHA: d54312dccb26f07614a2fe286a76ec9c27c7efa8
FINDINGS_COUNT: 1
