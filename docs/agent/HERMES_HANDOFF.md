# Hermes Handoff

## Current Branch
feature/phase-2-salon-operations

## Phase 1 Status
Checkpoint A-D PASS.
Checkpoint E belum selesai.

## Phase 2 Status
**P2-D STAFF WEEKLY AVAILABILITY API COMPLETED — READY FOR AUDIT**

### Checkpoint Status Summary
- P2-A: FINAL PASS
- P2-B: FINAL PASS
- P2-C: FINAL PASS
  - IMPLEMENTATION SHA: `0c869b3543f6846e87c3fe78528c0bcda70c300a`
  - REPORT/DOCS SHA: `96ae8cde2891f3c10699ba43f2c1f062ededf6f9`
- P2-D: READY FOR AUDIT
  - IMPLEMENTATION SHA: `cdeb8f1`
  - REPORT/DOCS SHA: `PENDING_COMMIT`
- P2-E: IN PROGRESS

### P2-D Deliverables
- ✓ Staff Weekly Availability CRUD API (`/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability`)
- ✓ RBAC: Owner/Manager manage any profile availability; Staff manage own profile only
- ✓ Read: all permitted tenant roles can read same-tenant availability
- ✓ Tenant isolation: cross-tenant profile/availability returns 404
- ✓ Validation: `day_of_week` (0..6), `start_time` < `end_time`
- ✓ Overlap protection: `new_start < existing_end AND new_end > existing_start` -> 409
- ✓ Adjacent intervals allowed; PATCH excludes own record
- ✓ DB IntegrityError mapping: `uq_staff_weekly_availability_staff_day_start` -> 409
- ✓ 22 new P2-D tests (206 total tests PASS)
- ✓ Ruff + Black quality gates PASS

### Endpoints (P2-D)
```
GET    /salons/{salon_id}/staff-profiles/{staff_profile_id}/availability
POST   /salons/{salon_id}/staff-profiles/{staff_profile_id}/availability
PATCH  /salons/{salon_id}/staff-profiles/{staff_profile_id}/availability/{availability_id}
DELETE /salons/{salon_id}/staff-profiles/{staff_profile_id}/availability/{availability_id}
```

### RBAC Matrix (Staff Weekly Availability)
| Action              | Owner | Manager | Staff |
|---------------------|-------|---------|-------|
| Create availability | ✓ any | ✓ any   | ✓ own |
| Read availability   | ✓     | ✓       | ✓     |
| Update availability | ✓ any | ✓ any   | ✓ own |
| Delete availability | ✓ any | ✓ any   | ✓ own |

## Next Action
Proceed immediately to **P2-E: Customer Records API**.
- Schema: `salon_customers` (existing P2-A)
- Endpoints: POST, GET (list), GET (detail), PATCH (no DELETE)
- RBAC: Owner, Manager, Staff can create/read/update
- Tenant isolation & duplicate email/phone policy: allowed, no auto-merge
- Full verification suite, report, and final handoff
