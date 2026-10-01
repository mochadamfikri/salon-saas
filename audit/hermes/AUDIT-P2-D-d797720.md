# Automated Audit — P2-D

- Source agent: hermes
- Source branch: feature/phase-2-salon-operations
- Base SHA: 96ae8cde2891f3c10699ba43f2c1f062ededf6f9
- Audited SHA: d797720
- Generated: 2026-10-01T07:33:04.542595+00:00

# Audit Report

- **Checkpoint:** P2-D — Staff Weekly Availability
- **Audited SHA:** `d7977206d8084b8f27aae2e7595109fd9025a503`
- **Scope inspected:** Commit range `96ae8cde2891f3c10699ba43f2c1f062ededf6f9..d797720`; availability router, service, schemas, model constraints, and API tests. P2-E was not evaluated.

**Findings**
- **Medium — PATCH accepts explicit `null` for availability fields.** `AvailabilityUpdateRequest` declares `day_of_week`, `start_time`, and `end_time` as nullable (`apps/api/app/schemas/availability.py:37`). The endpoint forwards explicitly supplied nulls to service validation (`apps/api/app/routers/availability.py:205`), where comparisons such as `new_start >= new_end` may raise `TypeError` instead of returning a deterministic client error (`apps/api/app/services/availability.py:194`). The master spec requires a valid weekday and `start_time < end_time`; null does not satisfy those constraints. Reject explicit nulls with 422. No PATCH-null regression test is present.

**Verification**
- Reviewed route-level tenant scoping, profile/slot association checks, staff-own-profile authorization, and owner/manager mutation access.
- Confirmed overlap predicate and PATCH self-exclusion in the service; tests cover overlap cases, adjacency, and self-exclusion.
- Confirmed named same-start constraint mapping rolls back before returning 409; unrelated `IntegrityError` is re-raised.
- Targeted tests were **not run**: `pytest` is unavailable in the audit environment. Broader tests and quality gates were not run for the same environment limitation.
- The audit worktree was clean and pinned to the requested SHA.

**Verdict Rationale**
The null PATCH handling is an actionable validation defect against the checkpoint’s constraints; targeted test verification was also unavailable. The checkpoint requires revision before pass.

AUDIT_VERDICT: REVISE
AUDITED_SHA: d7977206d8084b8f27aae2e7595109fd9025a503
FINDINGS_COUNT: 1