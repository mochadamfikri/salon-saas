# Salon SaaS — Phase 3 Master Spec
## Booking & Appointment Engine

**Execution state on upload:** `WAITING_DEPENDENCY` until Phase 2 is `FINAL_PASS`. Upload/validation/Owner approval may happen earlier.

## Purpose
Booking core: lifecycle, conflict engine, reschedule/cancel, calendar UI.

## Non-Negotiable Global Rules
- Inherit `policies/PROJECT_RULES.md`.
- Backend tenant/RBAC checks are authoritative; frontend role visibility is UX only.
- Browser → Next.js BFF → FastAPI. Never expose access/refresh tokens in browser JSON.
- Cross-tenant resources must not leak existence.
- Expected domain/client failures are deterministic; do not escape as HTTP 500.
- `READY_FOR_AUDIT` never unlocks a dependency; only `FINAL_PASS` does.
- Revision → re-audit → `FINAL_PASS` before any dependent task starts.
- No merge/deploy/destructive production action without Owner approval.
- Work one checkpoint at a time; do not pre-build later checkpoints.

## Dependency Gate
Phase 2 must be `FINAL_PASS` before the first Phase 3 task starts. Phase 4 remains locked until this phase closure is `FINAL_PASS`.

## Product Contract
`Appointment` is salon-scoped and links one SalonCustomer, one active SalonService, and one bookable StaffProfile assigned to that service. Required snapshots: service name, duration, price, currency. Store instants in UTC and retain IANA timezone used for local interpretation. `ends_at = starts_at + duration_snapshot`.

### Lifecycle
Canonical states: `scheduled`, `confirmed`, `completed`, `cancelled`, `no_show`. Allowed: scheduled→confirmed/cancelled/completed/no_show; confirmed→completed/cancelled/no_show. Terminal states cannot be reopened in Phase 3.

### Conflict / Availability
Creation and reschedule must validate staff-service assignment, `is_bookable`, weekly availability and no staff overlap. Overlap predicate: `new_start < existing_end AND new_end > existing_start`; adjacency allowed; cancelled appointments do not block. Race-safe server enforcement; conflict→409. Invalid input/time→422. Cross-tenant reference→404.

### Permissions
Owner/Manager/Staff may create/read/reschedule/status-change same-tenant appointments. Backend authorization remains authoritative. No public/customer booking yet.

### Endpoints
POST/GET `/salons/{salon_id}/appointments`; GET/PATCH `/salons/{salon_id}/appointments/{appointment_id}`; POST actions `/confirm`, `/complete`, `/cancel`, `/no-show`. No hard DELETE. List filters: date range, staff, customer, service, status; pagination required.

### P3-A
Models, migrations, snapshots, lifecycle validator, indexes, tenant invariants.
### P3-B
Timezone-aware availability resolver, capability validation, overlap/concurrency engine, adjacency tests.
### P3-C
Appointment API, filters, reschedule/cancel/status commands, idempotent-safe mutation behavior.
### P3-D
Mobile day/week calendar/list, create/reschedule/cancel/status UX, customer/service/staff picker, available-time UX, 404/409/422 handling via BFF.
### P3-E
Full regression: auth/session + P2 service/staff/availability/customer + booking lifecycle/timezone/concurrency + frontend production build.

## Out of Scope
Payments/POS, reminders, public booking, recurring appointments, waitlist, rooms/resources, multi-branch routing.

## Definition of Done
P3-A..P3-D audited FINAL_PASS and P3-E integration closure FINAL_PASS.
