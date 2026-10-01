# Phase 2 P2-D Completion Report — Weekly Availability

## Status
READY FOR AUDIT

## Implementation
- IMPLEMENTATION SHA: `cdeb8f1`
- Branch: `feature/phase-2-salon-operations`

## Files Changed
- `apps/api/app/main.py`
- `apps/api/app/routers/availability.py`
- `apps/api/app/schemas/availability.py`
- `apps/api/app/services/availability.py`
- `apps/api/tests/test_staff_availability.py`

## API Contract
- `GET /salons/{salon_id}/staff-profiles/{staff_profile_id}/availability`
- `POST /salons/{salon_id}/staff-profiles/{staff_profile_id}/availability`
- `PATCH /salons/{salon_id}/staff-profiles/{staff_profile_id}/availability/{availability_id}`
- `DELETE /salons/{salon_id}/staff-profiles/{staff_profile_id}/availability/{availability_id}`

## RBAC and Tenant Isolation
- Owner and manager can read and mutate availability for every same-tenant staff profile.
- Staff can read all same-tenant availability, but can create, update, and delete only slots belonging to their own `StaffProfile`.
- Own profile is derived from `StaffProfile.membership.user_id` and the authenticated tenant context.
- Profile and availability lookups are tenant-scoped. Cross-tenant resources return `404`.

## Validation and Overlap Semantics
- `day_of_week` is restricted to integer `0..6`.
- `start_time` must be earlier than `end_time`.
- The overlap predicate is `new_start < existing_end AND new_end > existing_start`.
- Exact, partial-left, partial-right, contained, and containing intervals return `409`.
- Adjacent intervals are allowed.
- PATCH excludes the record being updated from the overlap query.

## Database IntegrityError Handling
- The named unique constraint `uq_staff_weekly_availability_staff_day_start` is mapped to `409` after rolling back the session.
- Unrelated `IntegrityError` values are rolled back and re-raised through the existing unexpected-error path; they are not converted to `409`.

## Tests Added
`test_staff_availability.py` adds 22 API contract tests covering:
- owner/manager/staff create, update, and delete authorization
- staff own-profile restriction
- same-tenant reads for all roles
- cross-tenant resource hiding
- weekday and time-order validation
- overlap rejection and adjacent-slot allowance
- PATCH self-exclusion and overlap rejection
- expected duplicate and unrelated `IntegrityError` behavior

## Quality Gates
- `pytest -q`: PASS — 206 passed
- `ruff check .`: PASS
- `ruff format --check .`: PASS
- `black --check .`: PASS

## Known Warnings / Issues
- Existing test environment warnings remain: Starlette TestClient/httpx deprecation, SQLAlchemy transaction cleanup warnings in test fixtures, and FastAPI's deprecated `HTTP_422_UNPROCESSABLE_ENTITY` constant.
- No P2-D functional issue is known.
