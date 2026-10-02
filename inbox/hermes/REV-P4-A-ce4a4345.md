TARGET_AGENT: HERMES
TASK_ID: REV-P4-A-ce4a4345
PHASE: 4
CHECKPOINT: P4-A
TYPE: revision
PRIORITY: 5
AUTHORITATIVE_SHA: ce4a4345dd7e2d52cff2bccef5522c34df34fe0f
AUDIT_BASE_SHA: 58dd0a8c70798add0299288031c035873763650e
SOURCE_AUDIT_TASK: AUDIT-P4-A
AUDIT_REPORT: /home/ubuntu/salon-orchestrator/audit/hermes/AUDIT-P4-A-ce4a4345.md
STATUS: COMPLETED

Fix every blocking finding in the audit report below. Work on the current engineering branch, preserve later compatible work, run the required regression/quality gates, commit, push, update the completion/handoff report, then stop READY_FOR_AUDIT. Do not merge, deploy, change production, or invent business rules.

===== AUDIT REPORT =====
**Audit Report**
- Checkpoint: P4-A; audited SHA: `ce4a4345dd7e2d52cff2bccef5522c34df34fe0f`.
- Scope: reviewed the pinned revision diff, branch API/service/schema, model and migration, branch tests, and Phase 4 contract. Runtime status confirms Phase 3 is `FINAL_PASS`.
- Verification: trusted-host verifier reports `pytest` passed (335 tests), Ruff check/format passed, and Black passed. I did not rerun these gates locally.

**Finding**
- **High — Validate branch timezones.** `BranchCreateRequest` and `BranchUpdateRequest` accept any non-empty string for `timezone` (`apps/api/app/schemas/branch.py`). The branch service persists it unchanged (`apps/api/app/services/branch.py`). The existing appointment service validates IANA timezones before using them; an invalid branch timezone can therefore be saved and later break branch-aware scheduling. Validate the timezone on create and update, return a deterministic client error, and cover both paths with tests.

**Verdict**
- `REVISE`: the invalid-timezone persistence path remains unresolved. No other blocking findings identified in the inspected scope.

AUDIT_VERDICT: REVISE
AUDITED_SHA: ce4a4345dd7e2d52cff2bccef5522c34df34fe0f
FINDINGS_COUNT: 1
