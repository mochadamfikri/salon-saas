# P4-A Revision Report — REV-P4-A-d54312dc

**Revision Task:** REV-P4-A-d54312dc  
**Original Checkpoint:** P4-A (Branch Domain Foundation)  
**Audit Base SHA:** `58dd0a8c70798add0299288031c035873763650e`  
**Audited SHA:** `d54312dccb26f07614a2fe286a76ec9c27c7efa8`  
**Revision SHA:** `e99c38266d8e0f7e8f4c7e40edb34cf6b5f8e3e8`  
**Branch:** `feature/phase-4-branch-operations`

## Audit Finding

**High — Restrict IntegrityError mapping to specific constraint.**

`apps/api/app/routers/branch.py:56` mapped every `IntegrityError` during branch creation to "Branch code already exists" (409 Conflict). The project rules require that unrelated integrity failures not be disguised as business conflicts. Only the `uq_branches_salon_code` constraint violation should map to 409; other IntegrityError exceptions must propagate or be handled appropriately.

## Resolution

### Router Fix
**File:** `apps/api/app/routers/branch.py`

1. Added helper function following established codebase pattern:
```python
def _is_expected_duplicate_error(error: IntegrityError, constraint_name: str) -> bool:
    """Return whether an IntegrityError is the expected named UNIQUE constraint."""
    diagnostics = getattr(getattr(error, "orig", None), "diag", None)
    return getattr(diagnostics, "constraint_name", None) == constraint_name
```

2. Updated exception handler in `create_branch_endpoint`:
```python
except IntegrityError as error:
    tenant.db.rollback()
    if _is_expected_duplicate_error(error, "uq_branches_salon_code"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Branch code already exists in this salon",
        ) from None
    raise
```

This ensures only the specific `uq_branches_salon_code` unique constraint violation maps to 409 Conflict. Unrelated IntegrityError exceptions (foreign key violations, other constraints) now propagate unchanged, preventing misclassification of database errors as business conflicts.

### Regression Coverage
**File:** `apps/api/tests/test_branch.py`

Added new test class `TestBranchIntegrityErrorHandling` with two tests:

1. **`test_branch_duplicate_code_integrity_error_mapped_to_409`**:
   - Mocks `create_branch` to raise IntegrityError with `constraint_name = "uq_branches_salon_code"`
   - Verifies HTTP 409 Conflict response
   - Confirms error message contains "already exists"

2. **`test_unrelated_integrity_error_not_converted_to_409`**:
   - Mocks `create_branch` to raise IntegrityError with unrelated constraint name
   - Verifies IntegrityError propagates (not caught as 409)
   - Uses `pytest.raises(IntegrityError)` to assert exception escapes handler

## Verification

### Test Results
```
pytest -q: 339 passed in 169.07s (0:02:49)
```

New test count: 339 (was 337; +2 for deterministic IntegrityError handling tests)

### Quality Gates
- `ruff check .`: PASS
- `ruff format --check .`: PASS  
- `black --check .`: PASS

### Changed Files
- `apps/api/app/routers/branch.py` (constraint-specific error handling)
- `apps/api/tests/test_branch.py` (regression tests)

### Consistency with Existing Pattern
The `_is_expected_duplicate_error` helper matches the established pattern already used in:
- `apps/api/app/routers/staff_profile.py` (lines 33-36)
- `apps/api/app/routers/availability.py` (lines 28-31)

This ensures deterministic error handling is applied consistently across all domain routers per PROJECT_RULES.md validation requirements.

## Status
**READY_FOR_AUDIT**

The audit finding has been resolved. IntegrityError handling now restricts 409 Conflict mapping to the specific `uq_branches_salon_code` constraint violation, with full regression coverage ensuring unrelated database errors are not disguised as business conflicts.
