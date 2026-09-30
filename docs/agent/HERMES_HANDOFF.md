# Hermes Handoff

## Current Branch
feature/phase-2-salon-operations

## Phase 1 Status
Checkpoint A-D PASS.
Checkpoint E belum selesai.

## Phase 2 Status
**P2-A AUDIT REMEDIATION COMPLETED** ✓

### Audit Status
- Initial submission: BLOCKED (remote HEAD 84529b9)
- Remediation: COMPLETED
- Awaiting: Auditor re-review

### P2-A Remediation Deliverables
- ✓ Contract-compliant schema (all audit findings addressed)
- ✓ Migration 547d2dd43298 (clean, reversible)
- ✓ 20 contract compliance tests
- ✓ 129 total tests PASS (Phase 1 regression + Phase 2)
- ✓ Ruff + format PASS

### Schema Changes (Audit Remediation)
1. **salon_services**
   - Added: category (opt), currency DEFAULT 'IDR'
   - Added: CHECK(duration_minutes > 0), CHECK(price_amount >= 0)
   - Fixed: price_amount typing (Decimal)
   - Removed: UNIQUE(salon_id, name)

2. **staff_profiles**
   - Added: phone (opt)
   - Fixed: display_name now optional
   - Documented: SalonMembership is authoritative source

3. **staff_weekly_availability**
   - Changed: day_of_week 0-6 (was 1-7)
   - Added: CHECK(start_time < end_time), is_available boolean
   - Documented: UNIQUE prevents exact duplicates only, NOT overlap

4. **salon_customers**
   - Fixed: email and phone now optional
   - Removed: UNIQUE(salon_id, email)

5. **Tenant isolation**
   - Clarified: Application-layer invariant (P2-C enforcement)
   - Database provides FK relationships only

### Tables (Final Schema)
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
   - UNIQUE prevents exact duplicates only

5. **salon_customers** - customer per salon
   - email, phone OPTIONAL
   - No uniqueness constraints

## Next Action
**STOP - DO NOT START P2-B**

Awaiting auditor re-review of remediation.

After audit PASS:
- P2-B: Service & Staff Management API Endpoints

## Rules (Masih Berlaku)
- semua tenant-scoped via salon_id
- UUID, timestamps, PostgreSQL constraints
- gunakan TenantContext/RBAC Phase 1
- jangan booking engine dulu
- jangan payment/POS/inventory/payroll/attendance
- jangan frontend
- jangan production

## Last Commits
SHA: 5e573e3 - style: format migration file
SHA: 13a775d - fix(phase2): P2-A audit remediation - contract-compliant schema
SHA: 91755ee - fix(phase2): P2-A audit remediation - contract-compliant schema (pre-format)

**Remote HEAD:** 5e573e3cd39e9831bc62c4647a40a2727f2ef26c
