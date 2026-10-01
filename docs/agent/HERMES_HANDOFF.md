# Hermes Handoff

## Current Branch
feature/phase-3-booking-engine

## Phase 1 Status
Checkpoint A-D PASS.
Checkpoint E closure tracks separately.

## Phase 2 Status
**PHASE 2 CLOSURE: FINAL PASS** (audited under sha `c08e42d09407f8493e64e4ad8b21ff43c01b6e6d`)

## Phase 3 Status
**P3-A: READY FOR AUDIT**

### Checkpoint Status Summary
- P3-A (Booking Domain & Lifecycle): READY FOR AUDIT
  - Models: `Appointment` ORM model in `apps/api/app/models.py`
  - Migration: `9ecad5e4f77e_phase_3_booking_engine_core.py`
  - Lifecycle: `apps/api/app/services/appointment.py`
  - Tests: `apps/api/tests/test_appointment_p3a.py` (25 tests)
  - Report: `docs/reports/phase3-p3a-completion-report.md`
- P3-B (Availability & Capability): WAITING_DEPENDENCY
- P3-C (Appointment API): WAITING_DEPENDENCY
- P3-D (Calendar UI): WAITING_DEPENDENCY
- P3-E (Regression & Closure): WAITING_DEPENDENCY

## Total Test Count
246 tests PASS (Phase 1 + Phase 2 + P3-A suite)

## Quality Gates Status
- `pytest -q`: PASS (246 passed in 124.91s)
- `ruff check .`: PASS
- `ruff format --check .`: PASS
- `black --check .`: PASS

## Deliverables in P3-A
- `appointments` table with FK constraints to `salons`, `salon_customers`, `salon_services`, and `staff_profiles` (`RESTRICT` on delete).
- UTC instants `starts_at` and `ends_at` with check constraint `ends_at > starts_at`.
- IANA `timezone` column and validation via `zoneinfo`.
- Snapshots: `service_name_snapshot`, `duration_minutes_snapshot`, `price_amount_snapshot`, `currency_snapshot`.
- Check constraints: `duration_minutes_snapshot > 0`, `price_amount_snapshot >= 0`, `status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')`.
- Lookup indexes on foreign keys, `starts_at`, and multi-column combinations (`(salon_id, staff_profile_id, starts_at)`, `(salon_id, status, starts_at)`, `(salon_id, customer_id, starts_at)`, `(salon_id, service_id, starts_at)`).
- Canonical state machine: `scheduled` → `confirmed`/`cancelled`/`completed`/`no_show`; `confirmed` → `completed`/`cancelled`/`no_show`; terminal states cannot transition to different states.
- Tenant isolation: customer, service, and staff-profile salon ownership verified. Cross-tenant resources raise `CrossTenantResourceError`.

## Explicitly Deferred to Later Checkpoints
- P3-B: Service activation, staff bookability, staff-service assignment verification, weekly availability validation, overlap detection engine, and race-safe concurrency.
- P3-C: FastAPI routers, request/response schemas, filter params, pagination, and action endpoints (`/confirm`, `/complete`, `/cancel`, `/no-show`).
- P3-D: Frontend calendar UI, booking creation/rescheduling dialogs, BFF integration.

## Working Tree Status
Clean on branch `feature/phase-3-booking-engine`.
Pushed to `origin/feature/phase-3-booking-engine`.
