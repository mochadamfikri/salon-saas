# Phase 2 P2-C Audit Remediation Report

**Checkpoint:** P2-C Staff Profile + Staff-Service Assignment API  
**Branch:** `feature/phase-2-salon-operations`  
**Date:** 2026-09-30  
**Status:** READY FOR RE-AUDIT

---

## Scope

This remediation resolves the P2-C audit findings without expanding into P2-D:

1. Deleting a membership with an existing `StaffProfile` returns HTTP 409 rather than surfacing a database foreign-key `IntegrityError` as HTTP 500.
2. Suspending a membership with an existing `StaffProfile` remains supported.
3. Database-level UNIQUE violations during staff-profile and staff-service-assignment creation are mapped to HTTP 409.
4. Regression coverage verifies the intended lifecycle and conflict responses.
5. P2-C endpoint documentation now correctly states that the API exposes eight public endpoints.

---

## Changes

### Membership deletion lifecycle

`remove_member()` now rejects hard deletion when the membership has a `StaffProfile`. The operation does not mutate the session before it raises. The tenant endpoint maps this business conflict to HTTP 409 and instructs callers to suspend the membership instead.

The delete endpoint also maps a future or unexpected foreign-key `IntegrityError` during delete/commit to HTTP 409 after rolling back the session. Memberships without a profile retain the Phase 1 hard-delete behavior.

### Suspension lifecycle

No restriction was added to `update_member_status()`. A membership with a staff profile can be changed to `suspended`, preserving the profile and any operational history while revoking access.

### UNIQUE-conflict handling

The staff-profile and assignment create endpoints now handle `IntegrityError` raised either by service-layer flushes or endpoint commits. Only the expected named PostgreSQL constraints map to HTTP 409:

- `staff_profiles_membership_id_key`
- `uq_staff_service_assignments_staff_service`

Other integrity failures continue to propagate rather than being mislabeled as duplicate conflicts. The database session is rolled back before returning the expected conflict response.

### Documentation

`phase2-p2c-completion-report.md` corrects the public endpoint count from nine to eight.

---

## Regression Coverage

`apps/api/tests/test_p2c_audit_remediation.py` adds eight tests:

- Member with `StaffProfile` cannot be deleted: HTTP 409.
- Member with profile plus assignment cannot be deleted: HTTP 409.
- Member without profile remains deletable: HTTP 200.
- Member with profile can be suspended: HTTP 200 and membership remains present.
- Sequential duplicate profile request remains HTTP 409.
- Sequential duplicate assignment request remains HTTP 409.
- Simulated profile UNIQUE `IntegrityError` maps to HTTP 409.
- Simulated assignment UNIQUE `IntegrityError` maps to HTTP 409.

---

## Verification

Run from `apps/api` using `.venv`:

```text
pytest -v
184 passed, 23 warnings in 91.52s

ruff check .
All checks passed!

ruff format --check .
57 files already formatted

black --check .
57 files would be left unchanged.
```

The warnings are pre-existing test-environment deprecation/transaction warnings; there were no test failures.

---

## Result

P2-C remediation is complete. The branch contains no P2-D implementation and is ready for P2-C re-audit.
