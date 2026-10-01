# Salon SaaS — Phase 2 Master Spec

## Purpose
Phase 2 creates the salon operations foundation required before Booking. Booking/appointments are **not** Phase 2.

## Dependency Graph
P2-A Domain Foundation
- SalonService → P2-B
- StaffProfile + StaffServiceAssignment → P2-C
- StaffWeeklyAvailability → P2-D
- SalonCustomer → P2-E

P2-B + P2-C + P2-D + P2-E become dependencies of future Booking.

## Current Observed Status
### Backend
- P2-A: FINAL PASS
- P2-B: FINAL PASS
- P2-C: FINAL PASS
  - implementation `0c869b3543f6846e87c3fe78528c0bcda70c300a`
  - report/docs `96ae8cde2891f3c10699ba43f2c1f062ededf6f9`
- P2-D: READY FOR AUDIT at latest observed backend handoff
- P2-E: IN PROGRESS at latest observed backend handoff

### Frontend
- Phase 1 baseline: FINAL PASS
- P2-B Service Catalog: FINAL PASS
  - implementation `7b69f45a70fa3b58363697670948fd43ff758920`
  - report/docs HEAD `a16323e78da9e839994bc5eb548dd52779505267`
- P2-C: pending
- P2-D: pending
- P2-E: pending

Always refresh status from Git before dispatching work.

# P2-A — Domain Foundation
## SalonService
- salon_id
- name
- description nullable
- category nullable
- duration_minutes > 0
- price_amount `Numeric(12,2)`
- currency default IDR
- is_active
- timestamps
No forced unique `(salon_id, name)`.

## StaffProfile
One profile per membership. Fields include membership_id, display_name/phone/bio/photo_url nullable, is_bookable, timestamps. Salon/user ownership derives from membership.

## StaffServiceAssignment
Associates StaffProfile to SalonService and must remain inside one tenant.

## StaffWeeklyAvailability
- staff_profile_id
- day_of_week 0..6
- start_time
- end_time
- is_available
Constraints: `start_time < end_time`; unique `(staff_profile_id, day_of_week, start_time)`. UNIQUE is same-start guard only.

## SalonCustomer
- salon_id
- full_name required
- email nullable
- phone nullable
- notes nullable
- timestamps
No email/phone uniqueness in Phase 2.

# P2-B — Service Catalog
## Endpoints
- POST `/salons/{salon_id}/services`
- GET `/salons/{salon_id}/services`
- GET `/salons/{salon_id}/services/{service_id}`
- PATCH `/salons/{salon_id}/services/{service_id}`
- POST `/salons/{salon_id}/services/{service_id}/activate`
- POST `/salons/{salon_id}/services/{service_id}/deactivate`
No DELETE.

## RBAC
Owner/Manager: read + mutate. Staff: read only.

## PATCH
Nullable `description`, `category`: explicit null clears; omitted unchanged.
Required `name`, `duration_minutes`, `price_amount`, `currency`: explicit null => 422.

## Price
DB `Numeric(12,2)`, max `9999999999.99`; frontend preserves decimal string.

## Frontend
Owner/Manager mutation controls, Staff read-only, Browser → Next BFF → FastAPI, no token exposure, no DELETE UI.
Backend and frontend P2-B: FINAL PASS.

# P2-C — Staff Profile + Staff-Service Assignment
## Creation
StaffProfile explicit, not automatic. Owner/Manager creates from existing active membership. Eligible roles: owner, manager, staff.

## Lifecycle
No StaffProfile hard delete. `is_bookable=false` disables operationally; membership status/suspension controls access. Hard-delete membership with StaffProfile => 409.

## Read/Update
Owner/Manager read tenant profiles and update any. Staff reads tenant profiles and updates only own personal fields: display_name, phone, bio, photo_url. `is_bookable` Owner/Manager only. `membership_id` immutable.

## Assignment
Owner/Manager assign/unassign. Staff read-only. No bulk assignment.

## Tenant Invariant
`profile.membership.salon_id == service.salon_id == tenant.salon.id`; cross-tenant => 404.

## Concurrency
Duplicate StaffProfile => 409. Duplicate StaffServiceAssignment => 409. Relevant UNIQUE IntegrityError => rollback + 409. Unrelated IntegrityError is not relabeled.

Backend P2-C: FINAL PASS.

# P2-D — Weekly Availability
## Endpoints
- GET `/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability`
- POST `/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability`
- PATCH `/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability/{availability_id}`
- DELETE `/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability/{availability_id}`

## RBAC
Owner/Manager: read/manage any same-tenant profile. Staff: read same-tenant, mutate only own profile. Own profile iff `StaffProfile.membership.user_id == authenticated user id`.

## Validation
`day_of_week` 0..6; `start_time < end_time`.

## Overlap
For same StaffProfile/day: `new_start < existing_end AND new_end > existing_start`.
Existing 09:00–12:00 rejects 08:00–10:00, 10:00–13:00, 09:30–11:00, 08:00–13:00, 09:00–12:00. Allows 07:00–09:00 and 12:00–14:00. PATCH excludes current row. Overlap => 409.

## Concurrency
Relevant same-start UNIQUE violation => rollback + 409. Unrelated IntegrityError not mislabeled.

## Frontend Expectations
Weekly schedule display, add/edit/delete slot, owner/manager any-profile management, staff own-profile mutation, overlap UX, tenant-scoped BFF. No booking calendar/appointment engine.

# P2-E — Customer Records
## Endpoints
- POST `/salons/{salon_id}/customers`
- GET `/salons/{salon_id}/customers`
- GET `/salons/{salon_id}/customers/{customer_id}`
- PATCH `/salons/{salon_id}/customers/{customer_id}`
No DELETE.

## RBAC
Owner, Manager, Staff: create/read/update.

## Tenant Isolation
Salon ownership from path/TenantContext; client cannot move customer to another salon; cross-tenant => 404; no tenant leak.

## Validation
- `full_name`: required create, trim, non-empty; PATCH null => 422; omitted unchanged.
- `email`: optional, trim/lowercase, nullable/clearable; blank may normalize null if convention supports it.
- `phone`: optional, trim, nullable/clearable, no overly strict country format.
- `notes`: optional, nullable/clearable.

## Duplicate Policy
Duplicate email and phone allowed. No auto-merge or duplicate rejection merely due to same values. Dedup/merge deferred.

## Frontend Expectations
Customer list/create/detail/update, nullable clear semantics, full-name-only walk-in flow, duplicate email/phone allowed, tenant-scoped BFF, no DELETE UI.

# Phase 2 Definition of Done
Backend P2-A..P2-E must be auditor FINAL PASS.
Frontend required checkpoints P2-B..P2-E must be auditor FINAL PASS.
Final phase verification includes backend/frontend regressions, TypeScript, lint/format, production build, integration, tenant isolation and auth/session regression.

# Explicitly Out of Scope
Booking engine, booking conflict/holds/reschedule/cancel, payments/POS, inventory, payroll/attendance, commissions, expanded analytics/reporting, notification automation, packages/subscriptions, unrelated dashboard redesign.
