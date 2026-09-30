# Hermes Handoff

## Current Branch
feature/phase-2-salon-operations

## Phase 1 Status
Checkpoint A-D PASS.
Checkpoint E belum selesai.

## Phase 2 Status
**P2-C STAFF PROFILE + ASSIGNMENT API COMPLETED** ✓

### Completed Checkpoints
- ✓ P2-A: Schema/Models/Migration (audited, remediated, PASS)
- ✓ P2-B: Service Catalog API + RBAC + Tests
- ✓ P2-C: Staff Profile + Staff-Service Assignment API + RBAC + Tests

### P2-C Deliverables
- ✓ Staff Profile CRUD (explicit provisioning, not auto-created)
- ✓ Owner/Manager/Staff roles can have profiles (service providers)
- ✓ Personal fields update (staff own, owner/manager any)
- ✓ is_bookable toggle (owner/manager only)
- ✓ Staff-Service Assignment API
- ✓ Cross-salon invariant enforcement
- ✓ Assignment mutation: owner/manager only
- ✓ 32 P2-C tests + 176 total tests PASS
- ✓ Ruff + format PASS

### Endpoints (P2-C)
```
POST   /salons/{salon_id}/staff-profiles
GET    /salons/{salon_id}/staff-profiles
GET    /salons/{salon_id}/staff-profiles/{staff_profile_id}
PATCH  /salons/{salon_id}/staff-profiles/{staff_profile_id}
POST   /salons/{salon_id}/staff-profiles/{staff_profile_id}/toggle-bookable
POST   /salons/{salon_id}/staff-profiles/{staff_profile_id}/services/{service_id}
GET    /salons/{salon_id}/staff-profiles/{staff_profile_id}/services
DELETE /salons/{salon_id}/staff-profiles/{staff_profile_id}/services/{service_id}
```

### RBAC Matrix (Staff Profile)
| Action                | Owner | Manager | Staff |
|-----------------------|-------|---------|-------|
| Create profile        | ✓     | ✓       | ✗     |
| Read/list profiles    | ✓     | ✓       | ✓     |
| Update personal fields| ✓ any | ✓ any   | ✓ own |
| Toggle is_bookable    | ✓     | ✓       | ✗     |
| Assign service        | ✓     | ✓       | ✗     |
| Unassign service      | ✓     | ✓       | ✗     |
| Read assignments      | ✓     | ✓       | ✓     |

### Test Coverage (P2-C)
- Owner/Manager create profile (staff/manager/owner membership allowed)
- Staff cannot create own profile (403)
- Duplicate membership profile (409)
- Cross-salon membership (404)
- Suspended target membership rejected (422)
- Staff can update own personal fields
- Staff cannot update another profile (403)
- Owner/Manager can update any profile
- Staff cannot toggle is_bookable (403)
- Owner/Manager can toggle is_bookable
- Nullable fields can be cleared with explicit null
- membership_id immutable (422 extra field)
- Owner/Manager assign/unassign service
- Staff cannot assign/unassign (403)
- Duplicate assignment (409)
- Cross-salon profile/service (404)
- Service/profile tenant mismatch rejected

### Schema (P2-A - Unchanged)
1. **salon_services** - layanan salon
   - CHECK(duration_minutes > 0)
   - CHECK(price_amount >= 0)
   - currency DEFAULT 'IDR'
   - category OPTIONAL

2. **staff_profiles** - profil extended staff
   - UNIQUE(membership_id) - one-to-one
   - display_name, phone OPTIONAL

3. **staff_service_assignments** - many-to-many
   - UNIQUE(staff_profile_id, salon_service_id)

4. **staff_weekly_availability** - jadwal mingguan
   - CHECK(day_of_week BETWEEN 0 AND 6)
   - CHECK(start_time < end_time)
   - UNIQUE(staff_profile_id, day_of_week, start_time) is same-start collision guard; overlap protection in P2-D service layer

5. **salon_customers** - customer per salon
   - email, phone OPTIONAL
   - No uniqueness constraints

## Next Action
**STOP - AWAITING P2-C AUDIT**

After P2-C audit PASS:
- P2-D: Weekly Availability API
- P2-E: Customer Records API

## Rules (Masih Berlaku)
- semua tenant-scoped via salon_id
- UUID, timestamps, PostgreSQL constraints
- gunakan TenantContext/RBAC Phase 1
- jangan booking engine dulu
- jangan payment/POS/inventory/payroll/attendance
- jangan frontend
- jangan production

## Last Commits
SHA: a38e072 - feat(phase2): P2-C contract hardening - immutable field validation + manager update tests
SHA: a7f5a3c - feat(phase2): P2-C staff profile + staff-service assignment API + RBAC + tests
SHA: 96b2892 - docs: add P2-B audit remediation report

**Remote HEAD:** a38e07230a9e8747fabe7812aab4f2f64b923964
