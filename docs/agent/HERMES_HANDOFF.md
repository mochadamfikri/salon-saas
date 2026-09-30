# Hermes Handoff

## Current Branch
feature/phase-2-salon-operations

## Phase 1 Status
Checkpoint A-D PASS.
Checkpoint E belum selesai.

## Phase 2 Status
**P2-A COMPLETED** ✓

### P2-A Deliverables
- ✓ 5 tenant-scoped tables created
- ✓ Alembic migration 5497f90af712
- ✓ ORM models in app/models.py
- ✓ 6 schema constraint tests (PASS)
- ✓ 115 total tests PASS (Phase 1 regression + Phase 2)
- ✓ Ruff + Black PASS

### Tables Created
1. **salon_services** - layanan salon (haircut, facial, dll)
   - UNIQUE(salon_id, name)
   - FK salon_id → salons
2. **staff_profiles** - profil extended staff
   - UNIQUE(membership_id) - one-to-one dengan salon_memberships
   - FK membership_id → salon_memberships
3. **staff_service_assignments** - many-to-many staff ↔ services
   - UNIQUE(staff_profile_id, salon_service_id)
4. **staff_weekly_availability** - jadwal mingguan staff
   - CHECK(day_of_week BETWEEN 1 AND 7)
   - UNIQUE(staff_profile_id, day_of_week, start_time)
5. **salon_customers** - customer terdaftar per salon
   - UNIQUE(salon_id, email)

## Next Action
P2-B: Service & Staff Management API Endpoints
- POST /salons/{salon_id}/services
- GET /salons/{salon_id}/services
- PATCH /salons/{salon_id}/services/{service_id}
- DELETE /salons/{salon_id}/services/{service_id}
- POST /salons/{salon_id}/staff-profiles (create staff profile)
- GET /salons/{salon_id}/staff-profiles
- Tenant-scoped query enforcement
- RBAC: owner/manager untuk mutasi, staff read-only

## Rules (Masih Berlaku)
- semua tenant-scoped via salon_id
- UUID, timestamps, PostgreSQL constraints
- gunakan TenantContext/RBAC Phase 1
- jangan booking engine dulu
- jangan payment/POS/inventory/payroll/attendance
- jangan frontend
- jangan production

## Last Commit
SHA: f169506
Message: feat(phase2): P2-A Salon Operations Core - schema, migration, domain models
