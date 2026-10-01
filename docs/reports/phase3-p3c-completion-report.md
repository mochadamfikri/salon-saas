# Phase 3 P3-C Completion Report

## Status
READY FOR AUDIT

## Scope
P3-C — Booking API (Endpoints, filters, reschedule/cancel/status commands, idempotent-safe mutation behavior).

## Implementation Details

### Appointment Schemas (`apps/api/app/schemas/appointment.py`)
- `AppointmentCreateRequest`:
  - `customer_id: UUID`
  - `service_id: UUID`
  - `staff_profile_id: UUID`
  - `starts_at: datetime` (strictly validated as timezone-aware)
  - `timezone: str` (validated non-blank IANA string, max 64)
  - `notes: str | None` (trimmed, max 1000)
- `AppointmentUpdateRequest` (and alias `AppointmentRescheduleRequest`):
  - Optional `starts_at: datetime | None` (strictly validated as timezone-aware when provided)
  - Optional `timezone: str | None` (trimmed when provided)
  - Optional `notes: str | None` (trimmed)
- `AppointmentResponse`:
  - Full model representation including snapshot fields (`service_name_snapshot`, `duration_minutes_snapshot`, `price_amount_snapshot`, `currency_snapshot`), UTC instants (`starts_at`, `ends_at`), local IANA `timezone`, `status`, and timestamps (`created_at`, `updated_at`).

### Service Layer Enhancements (`apps/api/app/services/appointment.py`)
- `get_appointment(db, appointment_id, salon_id)`:
  - Scoped by `Appointment.salon_id == salon_id`, returning `None` if non-existent or belonging to another salon (404 boundary).
- `list_appointments(db, salon_id, ...)`:
  - Filters: `starts_at_gte`, `starts_at_lte` (normalized to UTC), `staff_profile_id`, `customer_id`, `service_id`, `appointment_status`.
  - Pagination: `offset` and `limit`.
  - Ordered deterministically by `starts_at, id`.
- `reschedule_appointment(db, appointment, starts_at, timezone_name, notes)`:
  - Rejects terminal states (`completed`, `cancelled`, `no_show`) with `TerminalStateError`.
  - Re-validates tenant boundaries, staff capability (`is_active`, `is_bookable`, assignment), weekly availability, advisory lock, and overlap check (with `exclude_appointment_id` allowing self-rescheduling).

### Router & Endpoints (`apps/api/app/routers/appointment.py`)
- `POST /salons/{salon_id}/appointments`:
  - Permitted: Owner, Manager, Staff in same salon.
  - Returns `201 Created` with `AppointmentResponse`.
  - Error mapping:
    - `CrossTenantResourceError` -> `404 Not Found`
    - `AppointmentCapabilityError` (`ServiceNotActiveError`, `StaffNotBookableError`, `StaffServiceAssignmentError`, `StaffNotAvailableError`) -> `422 Unprocessable Entity`
    - `AppointmentOverlapError` -> `409 Conflict`
- `GET /salons/{salon_id}/appointments`:
  - Permitted: Owner, Manager, Staff in same salon.
  - Supports query filters: `starts_at_gte`, `starts_at_lte`, `staff_profile_id`, `customer_id`, `service_id`, `status` (restricted to valid enum literals).
  - Supports pagination with `offset` and `limit` (max 100).
- `GET /salons/{salon_id}/appointments/{appointment_id}`:
  - Returns appointment detail if belonging to current salon, else `404 Not Found`.
- `PATCH /salons/{salon_id}/appointments/{appointment_id}`:
  - Reschedules appointment (when `starts_at` and `timezone` supplied) and/or updates `notes`.
  - Requires `starts_at` and `timezone` to be supplied together.
  - Terminal appointments cannot be rescheduled (`422 Unprocessable Entity`).
- Status Action Endpoints:
  - `POST /salons/{salon_id}/appointments/{appointment_id}/confirm`: transitions `scheduled` -> `confirmed`.
  - `POST /salons/{salon_id}/appointments/{appointment_id}/complete`: transitions `scheduled`/`confirmed` -> `completed`.
  - `POST /salons/{salon_id}/appointments/{appointment_id}/cancel`: transitions `scheduled`/`confirmed` -> `cancelled`.
  - `POST /salons/{salon_id}/appointments/{appointment_id}/no-show`: transitions `scheduled`/`confirmed` -> `no_show`.
  - Idempotent: transitioning an appointment to its existing state succeeds with `200 OK`.
  - Transitioning out of a terminal state is rejected with `422 Unprocessable Entity`.
- No hard DELETE endpoint (returns `405 Method Not Allowed`).

## Verification Evidence

### Test Suite Execution
- `pytest -q`: PASS (304 passed in 148.25s)
  - 31 comprehensive API contract tests in `test_appointment_p3c.py`
  - 27 availability and conflict tests in `test_appointment_p3b.py`
  - 25 domain model tests in `test_appointment_p3a.py`
  - 221 regression tests across Phase 1 and Phase 2 suites

### Quality Gates
- `ruff check .`: PASS (All checks passed)
- `ruff format --check .`: PASS (All files formatted)
- `black --check .`: PASS (All files formatted)

## Commits
- Implementation SHA: `0059845`
- Branch: `feature/phase-3-booking-engine`
- Remote: `origin/feature/phase-3-booking-engine`

## Explicitly Deferred to Later Checkpoints
- P3-D: Frontend calendar UI (day/week/list views), booking creation dialogs, customer/staff/service pickers, available-time UX, BFF error mapping.
- P3-E: End-to-end full regression and final phase audit closure.
