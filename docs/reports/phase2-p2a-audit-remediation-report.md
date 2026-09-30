# Phase 2 P2-A Audit Remediation Report

**Task:** P2-A Schema Audit Remediation  
**Branch:** `feature/phase-2-salon-operations`  
**Status:** ✓ COMPLETED  
**Date:** 2026-09-30  
**Final Commit:** `5e573e3cd39e9831bc62c4647a40a2727f2ef26c`

---

## Audit Decision

**Initial Submission:** P2-A (commits f169506, 6dc941c, 84529b9)  
**Audit Result:** REVISE / BLOCKED  
**Remote HEAD Auditor:** `84529b92cf337e06d07cc8ff6be3ed633d11b2c1`

---

## Remediation Summary

All audit findings addressed. Schema now contract-compliant with owner requirements.

### Changes Made

#### 1. SalonService

**Added:**
- `category` VARCHAR(100) NULLABLE (optional per contract)
- `currency` VARCHAR(3) NOT NULL DEFAULT 'IDR'
- CHECK(duration_minutes > 0)
- CHECK(price_amount >= 0)

**Fixed:**
- `price_amount` typing: `Mapped[Decimal]` (was incorrectly `Mapped[int]`)

**Removed:**
- UNIQUE(salon_id, name) - not an owner requirement

**Result:** Contract-compliant service schema with proper constraints.

---

#### 2. StaffProfile

**Added:**
- `phone` VARCHAR(20) NULLABLE

**Fixed:**
- `display_name` now NULLABLE (was incorrectly required)

**Documented:**
- SalonMembership is authoritative source for user_id and salon_id
- StaffProfile extends membership with operational booking metadata

**Result:** Flexible operational profile, optional fields per contract.

---

#### 3. StaffWeeklyAvailability

**Changed:**
- `day_of_week` range: 0-6 (was 1-7, now ISO 8601 compliant: Monday=0, Sunday=6)

**Added:**
- `is_available` BOOLEAN NOT NULL DEFAULT true
- CHECK(start_time < end_time)

**Documented:**
- UNIQUE(staff_profile_id, day_of_week, start_time) prevents exact duplicates ONLY
- Does NOT prevent overlapping time slots
- Full overlap protection scheduled for P2-D via application/service logic

**Result:** Contract-compliant availability with explicit overlap caveat.

---

#### 4. SalonCustomer

**Fixed:**
- `email` now NULLABLE
- `phone` now NULLABLE

**Removed:**
- UNIQUE(salon_id, email) - owner never mandated email uniqueness

**Documented:**
- Walk-in customers valid with name only
- Email/phone normalization is service-layer concern

**Result:** Flexible customer records, no invented uniqueness constraints.

---

#### 5. Tenant Isolation

**Clarified:**
- Database schema provides FK relationships
- Schema does NOT guarantee cross-salon assignment prevention at DB level
- Cross-salon assignment prevention is **application-layer invariant**
- To be enforced in P2-C with TenantContext + tests

**Decision:** Application-layer enforcement chosen over complex composite DB constraints to avoid duplicate source-of-truth and potential inconsistency.

---

## Migration

**New Migration:** `547d2dd43298_phase_2_salon_operations_core_v2.py`  
**Replaces:** `5497f90af712_phase_2_salon_operations_core.py` (deleted)

**Verification:**
- ✓ Clean base → head upgrade
- ✓ Phase 1 head → Phase 2 head upgrade
- ✓ Downgrade → Phase 1 head
- ✓ Re-upgrade → Phase 2 head

**No changes to Phase 1 migrations.**

---

## Test Coverage

**New Tests:** 20 contract compliance tests

**Coverage:**
- Service duration > 0 constraint
- Service price >= 0 constraint
- Currency defaults to IDR
- Category optional
- StaffProfile display_name optional
- StaffProfile phone optional
- Availability day 0 valid (Monday)
- Availability day 6 valid (Sunday)
- Availability day -1/7 invalid
- Availability start >= end rejected
- is_available boolean stored
- Customer name-only valid
- Customer email-only valid
- Customer phone-only valid
- No email uniqueness constraint
- Phase 1 regression intact

**Total:** 129 tests PASS (109 Phase 1 + 20 Phase 2)

---

## Code Quality

**Ruff:** All checks passed  
**Ruff Format:** 48 files formatted, 0 issues

---

## Git History

```
5e573e3 style: format migration file
13a775d fix(phase2): P2-A audit remediation - contract-compliant schema
91755ee fix(phase2): P2-A audit remediation - contract-compliant schema
84529b9 docs: add Phase 2 P2-A completion report
6dc941c docs: update HERMES_HANDOFF with P2-A completion status
f169506 feat(phase2): P2-A Salon Operations Core - schema, migration, domain models
```

**Branch:** `feature/phase-2-salon-operations`  
**Remote HEAD:** `5e573e3cd39e9831bc62c4647a40a2727f2ef26c`

---

## Verification Checklist

- [x] All audit findings addressed
- [x] Schema matches Phase 2 contract exactly
- [x] No invented business rules
- [x] Migration clean and reversible
- [x] 129 tests PASS (Phase 1 + Phase 2)
- [x] Ruff + format PASS
- [x] Committed and pushed
- [x] Documentation updated

---

## Final Schema Summary

### salon_services
- UUID id, salon_id FK, name, description, category (opt), duration_minutes, price_amount (Decimal), currency DEFAULT 'IDR', is_active, timestamps
- CHECK(duration_minutes > 0)
- CHECK(price_amount >= 0)

### staff_profiles
- UUID id, membership_id FK UNIQUE, display_name (opt), phone (opt), bio (opt), photo_url (opt), is_bookable, timestamps
- One-to-one with SalonMembership

### staff_service_assignments
- UUID id, staff_profile_id FK, salon_service_id FK, timestamps
- UNIQUE(staff_profile_id, salon_service_id)

### staff_weekly_availability
- UUID id, staff_profile_id FK, day_of_week (0-6), start_time, end_time, is_available, timestamps
- CHECK(day_of_week BETWEEN 0 AND 6)
- CHECK(start_time < end_time)
- UNIQUE(staff_profile_id, day_of_week, start_time) - exact duplicate protection only

### salon_customers
- UUID id, salon_id FK, full_name, email (opt), phone (opt), notes (opt), timestamps
- No uniqueness constraints on email/phone

---

## Status

**P2-A Audit Remediation:** ✓ PASS  
**Ready for:** Auditor re-review  
**Next:** P2-B (after audit approval)

---

**Report Generated:** 2026-09-30 13:49 UTC  
**Branch:** feature/phase-2-salon-operations  
**Final Commit:** 5e573e3cd39e9831bc62c4647a40a2727f2ef26c
