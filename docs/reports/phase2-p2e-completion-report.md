# Phase 2 P2-E Completion Report — Customer Records

## Status
READY FOR AUDIT

## Implementation
- IMPLEMENTATION SHA: `177fbbb`
- Branch: `feature/phase-2-salon-operations`

## Files Changed
- `apps/api/app/main.py`
- `apps/api/app/routers/customer.py`
- `apps/api/app/schemas/customer.py`
- `apps/api/app/services/customer.py`
- `apps/api/tests/test_customers.py`

## API Contract
- `POST /salons/{salon_id}/customers`
- `GET /salons/{salon_id}/customers`
- `GET /salons/{salon_id}/customers/{customer_id}`
- `PATCH /salons/{salon_id}/customers/{customer_id}`
- `DELETE` endpoint is absent (returns 405)

## RBAC Matrix
| Role    | Create Customer | List/Read Customer | Update Customer |
|---------|-----------------|--------------------|-----------------|
| Owner   | ✓               | ✓                  | ✓               |
| Manager | ✓               | ✓                  | ✓               |
| Staff   | ✓               | ✓                  | ✓               |

Staff is explicitly permitted to create and update customers for operational needs, including walk-in registrations and contact corrections.

## Tenant Isolation
- Customer records are scoped strictly via `salon_id` from the path and authenticated `TenantContext`.
- Client-supplied tenant fields in the payload are rejected (`extra="forbid"` on schemas).
- Cross-tenant requests return `404 Not Found`.
- Listing returns only records for the authenticated salon; no cross-tenant data leak is possible.

## Customer Validation and Normalization
- `full_name`: required on create, trimmed, non-blank; explicit null or blank on PATCH returns `422`; omitted on PATCH leaves existing name unchanged.
- `email`: optional, trimmed, converted to lowercase, nullable; blank string normalizes to `None`; explicit null on PATCH clears the field; omitted on PATCH leaves existing value unchanged.
- `phone`: optional, trimmed, nullable; blank string normalizes to `None`; explicit null on PATCH clears the field; omitted on PATCH leaves existing value unchanged.
- `notes`: optional, trimmed, nullable; blank string normalizes to `None`; explicit null on PATCH clears the field; omitted on PATCH leaves existing value unchanged.

## Duplicate Policy
- As per Phase 2 specifications, duplicate emails and phone numbers are ALLOWED.
- No auto-merge is performed.
- Customer deduplication/merging is deferred to a future phase.

## Tests Added
`test_customers.py` adds 11 API contract tests covering:
- Owner, manager, and staff create, read, and update permissions (parametrized across all 3 roles)
- Walk-in customers with `full_name` only
- Full name whitespace trimming, blank rejection, and null rejection
- Email trimming and lowercase normalization
- Phone trimming
- Nullable fields clearing with explicit null
- Omitted fields remaining unchanged on PATCH
- Duplicate email and duplicate phone allowance
- Cross-tenant resource hiding (`404`) and list isolation
- Rejection of salon_id spoofing
- Confirmation that DELETE endpoint is absent (`405 Method Not Allowed`)

## Quality Gates
- `pytest -q`: PASS — 217 passed in 124.64s
- `ruff check .`: PASS
- `ruff format --check .`: PASS
- `black --check .`: PASS

## Known Warnings / Issues
- Existing warnings from previous phases remain unchanged (Starlette TestClient deprecation warning, fixture transaction cleanup warnings, and FastAPI's deprecated HTTP_422 constant).
- No unresolved functional issues.
