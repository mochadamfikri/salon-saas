TARGET_AGENT: HERMES
TASK_ID: P3-E
PHASE: 3
CHECKPOINT: P3-E
TYPE: integration_closure
PRIORITY: 10
STATUS: WAITING_DEPENDENCY

DEPENDENCIES:
- P3-A:FINAL_PASS
- P3-B:FINAL_PASS
- P3-C:FINAL_PASS
- P3-D:FINAL_PASS

Read PROJECT_RULES + agent rules + PROJECT_MASTER_PLAN + PHASE3_MASTER_SPEC + BUSINESS_DECISIONS + audited dependencies.
Implement ONLY P3-E — Phase 3 Integration Closure. Do not implement later checkpoints/phases. Run required tests/quality gates, commit, push, write report/handoff, keep worktree clean, and stop READY_FOR_AUDIT. No merge/deploy.
