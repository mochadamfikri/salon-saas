# Phase 2 P2-D Audit Remediation Report

**Checkpoint:** P2-D — Staff Weekly Availability
**Branch:** `feature/phase-2-salon-operations`
**Audit task:** `REV-P2-D-d797720`
**Date:** 2026-10-01
**Status:** READY FOR AUDIT

## Audit Finding Resolved

The audited `AvailabilityUpdateRequest` accepted explicit `null` for `day_of_week`, `start_time`, and `end_time`. The PATCH route forwarded supplied values to the service, where a null time could reach the time-order comparison and cause a `TypeError` rather than a deterministic client validation response.

## Change

`AvailabilityUpdateRequest` now has a Pydantic before-model validator that rejects explicit `null` for all three constraint fields with HTTP 422 validation output.

- Omitting a field remains valid and leaves the persisted value unchanged.
- `day_of_week`, `start_time`, and `end_time` cannot be explicitly set to `null`.
- Service-layer time comparison is no longer reachable with null payload values through the API contract.

## Regression Coverage

`apps/api/tests/test_staff_availability.py` adds a parameterized PATCH regression test covering:

- `{"day_of_week": null}`
- `{"start_time": null}`
- `{"end_time": null}`
- all three fields explicitly null

Each request returns HTTP 422 after first creating a valid availability slot.

## Verification

Executed from `apps/api` using `/home/ubuntu/salon-saas/.venv`:

```text
pytest -q
221 passed, 25 warnings in 126.02s

ruff check .
All checks passed!

ruff format --check .
65 files already formatted

black --check .
65 files would be left unchanged.
```

Warnings are existing Starlette TestClient/httpx, SQLAlchemy fixture transaction cleanup, and deprecated FastAPI HTTP 422 constant warnings; no test failed.

## Commits

- `f55b3b3` — `fix(phase2): P2-D PATCH rejects explicit null for constraint fields`

## Result

The sole blocking P2-D audit finding is resolved. P2-D is READY FOR AUDIT; no phase expansion, merge, deployment, or production action was performed.
