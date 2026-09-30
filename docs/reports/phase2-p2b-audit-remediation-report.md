# Phase 2 Checkpoint P2-B Audit Remediation Report
**NULL Semantics + Decimal Validation**

**Date:** 2026-09-30  
**Branch:** feature/phase-2-salon-operations  
**Remote SHA:** 6d5a5946c23c5f61198852fd918f5c5951189396  
**Agent:** Hermes (Nous Research)  

---

## Executive Summary

P2-B audit remediation COMPLETED. All 4 audit findings addressed:
1. ✓ PATCH NULL semantics fixed (nullable fields clear, non-nullable reject 422)
2. ✓ Price Decimal validation consistent with DB (max_digits=12)
3. ✓ Documentation updated (HERMES_HANDOFF.md + completion report)
4. ✓ Verification complete (144 tests PASS, lint clean, working tree clean)

**Status:** READY FOR RE-AUDIT

---

## Audit Findings Addressed

### 1. PATCH NULL Semantics (FIXED)

**Problem:**
- `SalonServiceUpdateRequest` accepted None for all fields
- Router used `payload.model_dump(exclude_unset=True)`
- Service layer only assigned if `value is not None`
- Result: `PATCH {"description": null}` was silent no-op instead of clearing the field
- Result: `PATCH {"name": null}` was accepted but ignored instead of rejecting with 422

**Fix:**
```python
# apps/api/app/services/service_catalog.py
def update_service(db: Session, service: SalonService, **fields) -> SalonService:
    nullable_fields = {"description", "category"}
    required_fields = {"name", "duration_minutes", "price_amount", "currency"}
    
    for field_name, value in fields.items():
        if value is None and field_name in required_fields:
            raise ValueError(f"Field '{field_name}' cannot be set to null")
        
        if field_name in nullable_fields or field_name in required_fields:
            setattr(service, field_name, value)
    
    db.flush()
    db.refresh(service)
    return service
```

```python
# apps/api/app/routers/service.py
try:
    updated = update_service(tenant.db, service, **payload.model_dump(exclude_unset=True))
except ValueError as e:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
    ) from None
```

**Behavior After Fix:**
- `PATCH {"description": null}` → clears description to NULL (200)
- `PATCH {"category": null}` → clears category to NULL (200)
- `PATCH {"name": null}` → 422 "Field 'name' cannot be set to null"
- `PATCH {"duration_minutes": null}` → 422
- `PATCH {"price_amount": null}` → 422
- `PATCH {"currency": null}` → 422
- Omitted fields remain unchanged (partial update semantics preserved)

**Tests Added:**
1. `test_patch_can_clear_nullable_fields_with_explicit_null`
2. `test_patch_rejects_null_for_non_nullable_fields`

---

### 2. Price DB/Pydantic Consistency (FIXED)

**Problem:**
- DB: `Numeric(12, 2)` (max 10 integer digits + 2 decimal)
- Schema: `Decimal(ge=0, decimal_places=2)` but no max_digits
- Result: Oversized prices rejected by PostgreSQL instead of validation layer

**Fix:**
```python
# apps/api/app/schemas/service.py
class SalonServiceCreateRequest(BaseModel):
    price_amount: Decimal = Field(ge=0, decimal_places=2, max_digits=12)

class SalonServiceUpdateRequest(BaseModel):
    price_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
```

**Behavior After Fix:**
- `POST {"price_amount": "12345678901.00"}` → 422 (13 digits total, exceeds max_digits=12)
- `PATCH {"price_amount": "99999999999.99"}` → 422 (13 digits total)
- Valid: `"9999999999.99"` (12 digits total) → accepted

**Test Added:**
3. `test_oversized_decimal_rejected`

---

### 3. Documentation Cleanup (FIXED)

**Changes:**

#### HERMES_HANDOFF.md
- Updated remote HEAD from a9d603c to 6d5a594
- Fixed availability UNIQUE wording:
  - Before: "UNIQUE prevents exact duplicates only"
  - After: "UNIQUE(staff_profile_id, day_of_week, start_time) is same-start collision guard; overlap protection in P2-D service layer"
- Updated Last Commits section with remediation SHA

#### phase2-p2b-completion-report.md
- Updated test count breakdown to distinguish Phase 1+P2-A (129), P2-B original (12), remediation (3)
- Updated Git Status to reflect remediation commit
- Updated quality gates (Black version, format count)
- Removed premature "auditor PASS" claim (waiting for re-audit)

---

### 4. Verification (COMPLETE)

**Test Results:**
```
144 passed, 20 warnings in 45.85s
```

**Breakdown:**
- Phase 1 + P2-A: 129 tests (no regression)
- P2-B original: 12 tests (no regression)
- P2-B remediation: 3 tests (NEW, all PASS)

**Regression Tests:**
1. `test_patch_can_clear_nullable_fields_with_explicit_null` - PASS
   - Create service with description + category
   - PATCH description → null (clears to NULL)
   - PATCH category → null (clears to NULL)
   - Verify other fields unchanged

2. `test_patch_rejects_null_for_non_nullable_fields` - PASS
   - PATCH name → null (422)
   - PATCH duration_minutes → null (422)
   - PATCH price_amount → null (422)
   - PATCH currency → null (422)

3. `test_oversized_decimal_rejected` - PASS
   - POST with 13-digit price → 422
   - PATCH with 13-digit price → 422

**Lint & Format:**
- Ruff check: All checks passed
- Ruff format: 52 files already formatted
- Black: Available (24.10.0)

**No Migration Required:**
- Schema unchanged (DB constraints already correct)
- Remediation only touched validation layer and service logic

---

## Files Modified

### Code Changes
1. **apps/api/app/schemas/service.py**
   - Added `max_digits=12` to SalonServiceCreateRequest.price_amount
   - Added `max_digits=12` to SalonServiceUpdateRequest.price_amount

2. **apps/api/app/services/service_catalog.py**
   - Refactored `update_service()` signature from explicit params to `**fields`
   - Added nullable_fields and required_fields distinction
   - Reject None for required fields with ValueError
   - Allow None for nullable fields (clears to NULL)

3. **apps/api/app/routers/service.py**
   - Wrapped `update_service()` call in try-except
   - Catch ValueError → HTTPException 422

4. **apps/api/tests/test_service_catalog.py**
   - Added 3 regression tests (118 lines added)

### Documentation Changes
5. **docs/agent/HERMES_HANDOFF.md**
   - Updated remote HEAD to 6d5a594
   - Fixed availability UNIQUE wording
   - Updated Last Commits section

6. **docs/reports/phase2-p2b-completion-report.md**
   - Updated test count breakdown
   - Updated Git Status section
   - Updated quality gates

---

## Git History

```
6d5a594 docs: update HERMES_HANDOFF with final remediation SHA
3b18ebe fix(phase2): P2-B audit remediation - NULL semantics + Decimal validation
5036992 feat(phase2): P2-B service catalog API + RBAC + tests
a9d603c docs: P2-A audit remediation completion report
```

**Remediation Commit (3b18ebe):**
```
fix(phase2): P2-B audit remediation - NULL semantics + Decimal validation

- PATCH NULL semantics: nullable fields (description, category) clear with explicit null
- Non-nullable fields (name, duration, price, currency) reject null with 422
- Added max_digits=12 to price validation (consistency with DB Numeric(12,2))
- 3 new regression tests: clear nullable, reject null non-nullable, oversized Decimal
- 144 total tests PASS (no regression)
- Ruff + format PASS

Addresses audit findings:
1. PATCH explicit null now properly handled (nullable clear, non-nullable 422)
2. Price validation consistent with DB Numeric(12,2) constraint
3. Documentation updated (HERMES_HANDOFF.md remote HEAD + availability wording)
4. Completion report reflects remediation status
```

---

## Contract Guarantees After Remediation

### PATCH Semantics
| Field             | Nullable | Explicit null | Omitted   | Non-null value |
|-------------------|----------|---------------|-----------|----------------|
| name              | No       | 422           | unchanged | updated        |
| description       | Yes      | cleared       | unchanged | updated        |
| category          | Yes      | cleared       | unchanged | updated        |
| duration_minutes  | No       | 422           | unchanged | updated        |
| price_amount      | No       | 422           | unchanged | updated        |
| currency          | No       | 422           | unchanged | updated        |

### Price Validation
- **Range:** 0.00 to 9999999999.99 (10 integer digits + 2 decimal)
- **Total digits:** max 12 (enforced by Pydantic `max_digits=12`)
- **Database:** Numeric(12,2) (consistent with schema)
- **Rejection:** Client-side validation (422) before DB constraint

### Backward Compatibility
- No breaking changes to existing API contracts
- Previously working requests still work
- Previously silent bugs now properly rejected with 422
- Phase 1 and P2-A tests remain PASS (no regression)

---

## Verification Checklist

- [x] PATCH nullable fields can be cleared with explicit null
- [x] PATCH non-nullable fields reject null with 422
- [x] Omitted fields remain unchanged (partial update preserved)
- [x] Oversized Decimal rejected at validation layer (422)
- [x] Create and PATCH both enforce max_digits=12
- [x] 3 regression tests added and PASS
- [x] 144 total tests PASS (no regression)
- [x] Ruff check PASS
- [x] Ruff format PASS
- [x] Working tree clean
- [x] HERMES_HANDOFF.md updated
- [x] phase2-p2b-completion-report.md updated
- [x] Committed and pushed to remote
- [x] No schema migration required

---

## Next Action

**STOP - AWAITING RE-AUDIT**

P2-B audit remediation complete. All 4 findings addressed with regression tests and documentation updates. 144 tests PASS, lint clean, working tree clean.

After re-audit PASS:
- P2-C: Staff Profile + Staff-Service Assignment API
- P2-D: Weekly Availability API
- P2-E: Customer Records API

---

**Report Path:** `/home/ubuntu/salon-saas/docs/reports/phase2-p2b-audit-remediation-report.md`  
**Branch:** feature/phase-2-salon-operations  
**Remote HEAD:** 6d5a5946c23c5f61198852fd918f5c5951189396  
**Working Tree:** Clean  
**Status:** READY FOR RE-AUDIT ✓
