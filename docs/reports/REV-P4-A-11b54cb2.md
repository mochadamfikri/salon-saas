# P4-A Revision Report — REV-P4-A-11b54cb2

**Revision Task:** REV-P4-A-11b54cb2  
**Original Checkpoint:** P4-A (Branch Domain Foundation)  
**Audit Base SHA:** `58dd0a8c70798add0299288031c035873763650e`  
**Audited SHA:** `11b54cb28654ba6ecf79ff917e25b12c514908bc`  
**Branch:** `feature/phase-4-branch-operations`

## Audit Finding

**Medium — Update accepts an address longer than the database column.**

`BranchUpdateRequest.address` had no maximum length constraint, while `branches.address` is limited to 500 characters. This allowed clients to submit overlong addresses that would raise database errors rather than returning deterministic validation responses.

## Resolution

### Schema Fix
**File:** `apps/api/app/schemas/branch.py`

Changed `BranchUpdateRequest.address` from:
```python
address: str | None = None
```

To:
```python
address: str | None = Field(default=None, max_length=500)
```

This enforces the 500-character limit at the schema validation layer, matching the database constraint and ensuring deterministic 422 responses for overlong input.

### Regression Coverage
**File:** `apps/api/tests/test_branch.py`

Added `test_update_branch_rejects_overlong_address`:
- Creates a branch in the test tenant
- Attempts update with 501-character address
- Verifies HTTP 422 response

## Verification

### Test Results
```
pytest -q: 335 passed in 168.61s
```

New test count: 335 (was 334; +1 for address validation test)

### Quality Gates
- `ruff check .`: PASS
- `ruff format --check .`: PASS  
- `black --check .`: PASS

### Changed Files
- `apps/api/app/schemas/branch.py` (schema constraint)
- `apps/api/tests/test_branch.py` (regression test)

## Status
**READY_FOR_AUDIT**

The audit finding has been resolved. Address validation now enforces the database column limit deterministically at the schema layer, with regression coverage ensuring the constraint is verified.
