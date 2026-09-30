# Hermes Handoff

## Current Branch
feature/phase-2-salon-operations

## Phase 1 Status
Checkpoint A-D PASS.
Checkpoint E belum selesai.

## Phase 2 Status
**P2-B SERVICE CATALOG API COMPLETED** ✓

### Completed Checkpoints
- ✓ P2-A: Schema/Models/Migration (audited, remediated, PASS)
- ✓ P2-B: Service Catalog API + RBAC + Tests

### P2-B Deliverables
- ✓ Service Catalog API (POST/GET/PATCH + activate/deactivate)
- ✓ RBAC enforcement (Owner/Manager mutation, Staff read-only)
- ✓ Tenant isolation (cross-tenant 404, suspended denied)
- ✓ Contract validation (duration>0, price>=0, currency default IDR)
- ✓ 12 P2-B tests + 141 total tests PASS
- ✓ Ruff + format PASS

### Endpoints (P2-B)
```
POST   /salons/{salon_id}/services
GET    /salons/{salon_id}/services
GET    /salons/{salon_id}/services/{service_id}
PATCH  /salons/{salon_id}/services/{service_id}
POST   /salons/{salon_id}/services/{service_id}/activate
POST   /salons/{salon_id}/services/{service_id}/deactivate
```

### RBAC Matrix (Service Catalog)
| Action          | Owner | Manager | Staff |
|-----------------|-------|---------|-------|
| Create service  | ✓     | ✓       | ✗     |
| Read service    | ✓     | ✓       | ✓     |
| Update service  | ✓     | ✓       | ✗     |
| Activate        | ✓     | ✓       | ✗     |
| Deactivate      | ✓     | ✓       | ✗     |

### Test Coverage (P2-B)
- Owner/Manager create service (with defaults & optional fields)
- Staff create denied (403)
- Owner/Manager update service
- Staff update denied (403)
- Owner/Manager activate/deactivate lifecycle
- Staff activate/deactivate denied (403)
- Staff read service & list (success)
- Cross-tenant isolation (404)
- Suspended membership denied (404)
- Invalid duration rejected (422)
- Negative price rejected (422)
- Client cannot override salon_id (path authority)

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
**STOP - AWAITING AUDIT**

After P2-B audit PASS:
- P2-C: Staff Profile + Staff-Service Assignment API
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
SHA: 3fa834d - fix(phase2): P2-B audit remediation - NULL semantics + Decimal validation
SHA: 5036992 - feat(phase2): P2-B service catalog API + RBAC + tests
SHA: a9d603c - docs: P2-A audit remediation completion report

**Remote HEAD (pending push):** 3fa834d0c466f041b95197f32a2b7456a140a2fa
