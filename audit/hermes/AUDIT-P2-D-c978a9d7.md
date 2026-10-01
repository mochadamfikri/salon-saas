# Automated Audit — P2-D

- Source agent: hermes
- Source branch: feature/phase-2-salon-operations
- Base SHA: 96ae8cde2891f3c10699ba43f2c1f062ededf6f9
- Audited SHA: c978a9d79c1fa7ff9ab3b8647f715e3a9a51466d
- Generated: 2026-10-01T08:56:40.403330+00:00

**Audit Report**
- Checkpoint: P2-D — Staff Weekly Availability
- Audited SHA: `c978a9d79c1fa7ff9ab3b8647f715e3a9a51466d`
- Scope: Reviewed P2-D routes, schemas, services, model constraint, tests, and remediation diff against the P2-D contract. P2-E changes were not evaluated except as part of the supplied regression evidence.
- Implementation evidence: Tenant-scoped profile/availability lookups return 404 for cross-tenant resources; staff mutation checks derive ownership from the profile membership. Overlap uses the specified strict interval predicate, permits adjacency, and PATCH excludes the current slot. PATCH explicit nulls receive 422. The named unique constraint is mapped to 409 after rollback; unrelated integrity errors are not converted to conflicts.
- Tests/gates: The supplied trusted-host verifier reports 221 tests passed and Ruff, Ruff format, and Black checks passed at the audited SHA. My targeted `pytest -q tests/test_staff_availability.py` could not initialize because this sandbox lacks `DATABASE_URL`, `REDIS_URL`, and `JWT_SECRET`; this is an environment limitation, not contrary test evidence.
- Findings: None. Residual note: targeted tests were not independently rerun in this environment.
- Verdict rationale: Source and supplied pinned verification evidence satisfy the P2-D contract; no unresolved checkpoint finding remains.

AUDIT_VERDICT: PASS
AUDITED_SHA: c978a9d79c1fa7ff9ab3b8647f715e3a9a51466d
FINDINGS_COUNT: 0