# AUTONOMOUS FINAL REVIEW RULES

The final gate is conservative and deterministic.

It may promote PASS_CANDIDATE to FINAL_PASS only when ALL are true:
1. Auto Auditor state is PASS_CANDIDATE.
2. The pinned audit report exists.
3. The report explicitly contains AUDIT_VERDICT: PASS.
4. The report explicitly contains FINDINGS_COUNT: 0.
5. The report AUDITED_SHA exactly equals the task authoritative SHA.
6. A source implementation/revision task for the same checkpoint exists at the exact SHA.
7. The audited SHA is present on the expected source branch.
8. For frontend checkpoints, branch HEAD must exactly equal the audited SHA.

It never converts REVISE_REQUIRED or BLOCKED to FINAL_PASS.
If proof is missing or inconsistent, it keeps the checkpoint unapproved and raises OWNER_ACTION_REQUIRED.
