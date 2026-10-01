# Phase 3 P3-A Completion Report

## Status
READY FOR AUDIT

## Scope
P3-A — Booking Domain & Lifecycle only.

## Implementation

### Appointment persistence domain
- Added `Appointment` ORM model in `apps/api/app/models.py`.
- Added Alembic migration `9ecad5e4f77e_phase_3_booking_engine_core.py`.
- The `appointments` table is salon-scoped and references `salons`, `salon_customers`, `salon_services`, and `staff_profiles` with `RESTRICT` foreign keys.
- Stores timezone-aware UTC instants in `starts_at` and `ends_at`, plus required IANA `timezone` for local interpretation.
- Captures immutable booking-time service snapshots: name, duration, price, and currency.
- Enforces positive snapshot duration, non-negative snapshot price, valid time ordering, and canonical status values at DB level.

### Lifecycle domain service
- Added `apps/api/app/services/appointment.py`.
- Canonical lifecycle states: `scheduled`, `confirmed`, `completed`, `cancelled`, `no_show`.
- Allowed transitions match the Phase 3 contract:
  - `scheduled` → `confirmed`, `cancelled`, `completed`, `no_show`
  - `confirmed` → `completed`, `cancelled`, `no_show`
  - terminal states cannot transition to a different state
  - same-state transitions are idempotent.
- Validates IANA timezone identifiers and rejects naive start datetimes.
- Validates customer, service, and staff-profile tenant ownership before appointment persistence; cross-tenant or missing references raise a deterministic domain error for P3-C HTTP mapping.
- Computes `ends_at` from the service duration snapshot.

### Query indexes
- Added indexes for tenant, customer, service, staff profile, start time, and expected tenant-filtered booking query patterns.

## Explicitly deferred
- Service activation, staff bookability, service assignment, weekly availability, overlap checks, and race-safe conflict handling are P3-B.
- FastAPI endpoints, RBAC transport mapping, filtering/pagination, actions, and HTTP error mapping are P3-C.
- No frontend work, dashboard, calendar UI, payment, notification, or public booking functionality was added.

## Tests
- New `apps/api/tests/test_appointment_p3a.py`: 25 tests covering lifecycle transitions, terminal-state protection, IANA validation, snapshots, UTC-aware input enforcement, tenant isolation, and indexed query patterns.
- Updated migration regression test for Alembic revision `9ecad5e4f77e` and the `appointments` table.

## Quality gates
- `pytest -q`: PASS — 246 passed, 25 known non-blocking warnings.
- `ruff check .`: PASS.
- `ruff format --check .`: PASS.
- `black --check .`: PASS.

## Migration verification
- Upgrade to head: PASS.
- Downgrade one revision then re-upgrade to head: PASS.
- Isolated clean-database migration regression: PASS.

## Commit
- Implementation SHA: `79de221`
- Documentation SHA: `139c9f1`
- Formatting SHA: `0d69d20`
- Branch HEAD: `0d69d20` (pushed to `origin/feature/phase-3-booking-engine`)

## Audit request
P3-A is complete and ready for audit. It does not claim FINAL_PASS.
