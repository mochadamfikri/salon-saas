TARGET_AGENT: HERMES
TASK_ID: REV-P4-A-11b54cb2
PHASE: 4
CHECKPOINT: P4-A
TYPE: revision
PRIORITY: 5
AUTHORITATIVE_SHA: 11b54cb28654ba6ecf79ff917e25b12c514908bc
AUDIT_BASE_SHA: 58dd0a8c70798add0299288031c035873763650e
SOURCE_AUDIT_TASK: AUDIT-P4-A
AUDIT_REPORT: /home/ubuntu/salon-orchestrator/audit/hermes/AUDIT-P4-A-11b54cb2.md
STATUS: QUEUED

Fix every blocking finding in the audit report below. Work on the current engineering branch, preserve later compatible work, run the required regression/quality gates, commit, push, update the completion/handoff report, then stop READY_FOR_AUDIT. Do not merge, deploy, change production, or invent business rules.

===== AUDIT REPORT =====
**Audit Report**
- Checkpoint: P4-A; audited SHA: `11b54cb28654ba6ecf79ff917e25b12c514908bc`
- Scope: P4-A changes from base `58dd0a8c70798add0299288031c035873763650e` (branch model, API, schemas, migration, tests), plus current source and the Phase 4 contract. The pinned diff itself updates only the handoff; P4-A implementation is in earlier commit `c7b2f81`.
- Prior dependency: Phase 3 is `FINAL_PASS` in the authoritative runtime status.
- Verification: Trusted-host suite reports `334 passed`; Ruff check, Ruff format, and Black all pass. I did not rerun these gates locally.

**Findings**
- **Medium — Update accepts an address longer than the database column.** `BranchUpdateRequest.address` has no maximum length, while `branches.address` is limited to 500 characters. `update_branch` persists the supplied value, so an overlong update can raise a database error rather than a deterministic client response. Add a 500-character schema limit and regression coverage. Evidence: `apps/api/app/schemas/branch.py` (`BranchUpdateRequest`) and `apps/api/app/models.py:464`.

**Verdict**
- Tenant scoping, cross-tenant 404 behavior, mutation RBAC, and default-branch migration were inspected. The update validation defect remains actionable, so this checkpoint requires revision before passing.

AUDIT_VERDICT: REVISE
AUDITED_SHA: 11b54cb28654ba6ecf79ff917e25b12c514908bc
FINDINGS_COUNT: 1
