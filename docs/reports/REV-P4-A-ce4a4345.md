# P4-A Revision Report — REV-P4-A-ce4a4345

**Revision Task:** REV-P4-A-ce4a4345  
**Original Checkpoint:** P4-A (Branch Domain Foundation)  
**Audit Base SHA:** `58dd0a8c70798add0299288031c035873763650e`  
**Audited SHA:** `ce4a4345dd7e2d52cff2bccef5522c34df34fe0f`  
**Revision SHA:** `88a6ffb651537ed5b68b2e9fa22543055b3179cd`  
**Branch:** `feature/phase-4-branch-operations`

## Audit Finding

**High — Validate branch timezones.**

`BranchCreateRequest` and `BranchUpdateRequest` accepted any non-empty string for the `timezone` field without IANA timezone validation. The branch service persisted these values unchanged. Since the existing appointment service validates IANA timezones before using them, an invalid branch timezone could be saved and later break branch-aware scheduling when Phase 4-C integrates appointments with branches.

## Resolution

### Schema Validation
**File:** `apps/api/app/schemas/branch.py`

1. Added import:
```python
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
```

2. Added timezone validator to `BranchCreateRequest`:
```python
@field_validator("timezone")
@classmethod
def validate_timezone(cls, value: str) -> str:
    """Validate IANA timezone identifier."""
    try:
        ZoneInfo(value)
        return value
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid IANA timezone: '{value}'") from exc
```

3. Added timezone validator to `BranchUpdateRequest`:
```python
@field_validator("timezone")
@classmethod
def validate_timezone(cls, value: str | None) -> str | None:
    """Validate IANA timezone identifier."""
    if value is None:
        return value
    try:
        ZoneInfo(value)
        return value
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid IANA timezone: '{value}'") from exc
```

This ensures that invalid IANA timezone identifiers are rejected at the schema validation layer with deterministic HTTP 422 responses, preventing invalid timezone persistence.

### Regression Coverage
**File:** `apps/api/tests/test_branch.py`

Added two new regression tests:

1. **`test_create_branch_invalid_timezone_rejected`**:
   - Attempts to create a branch with invalid timezone `"InvalidZone/NotReal"`
   - Verifies HTTP 422 response
   - Confirms error message references timezone

2. **`test_update_branch_invalid_timezone_rejected`**:
   - Creates a valid branch with `"Asia/Jakarta"` timezone
   - Attempts to update timezone to invalid `"Not/A/Real/Zone"`
   - Verifies HTTP 422 response
   - Confirms error message references timezone

## Verification

### Test Results
```
pytest -q: 337 passed in 166.69s (0:02:46)
```

New test count: 337 (was 335; +2 for timezone validation tests on create and update paths)

### Quality Gates
- `ruff check .`: PASS
- `ruff format --check .`: PASS  
- `black --check .`: PASS

### Changed Files
- `apps/api/app/schemas/branch.py` (timezone validators)
- `apps/api/tests/test_branch.py` (regression tests)

### Consistency with Existing Pattern
The timezone validation implementation matches the pattern already established in `apps/api/app/services/appointment.py::validate_iana_timezone()`, which uses `ZoneInfo()` validation and raises `ValueError` for invalid IANA timezone identifiers. This ensures consistency across the codebase and prevents invalid timezones from being persisted to the database.

## Status
**READY_FOR_AUDIT**

The audit finding has been resolved. Branch timezone validation now enforces IANA timezone compliance deterministically at the schema layer for both create and update operations, with full regression coverage.
