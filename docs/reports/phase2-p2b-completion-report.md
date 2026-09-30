# Phase 2 Checkpoint P2-B Completion Report
**Service Catalog API + RBAC + Tests**

**Date:** 2026-09-30  
**Branch:** feature/phase-2-salon-operations  
**Agent:** Hermes (Nous Research)  

---

## Executive Summary

P2-B Service Catalog API implementation COMPLETED and ready for audit.

**Deliverables:**
- Service Catalog REST API (6 endpoints)
- RBAC enforcement (Owner/Manager mutation, Staff read-only)
- Tenant isolation + cross-tenant security
- Contract validation (duration>0, price>=0, defaults)
- 12 comprehensive P2-B tests
- 141 total tests PASS (no Phase 1 regression)
- Ruff + format PASS

**Scope Adherence:**
- P2-B focused ONLY on Service Catalog API
- NO Staff Profile/Assignment/Availability/Customer APIs (P2-C/D/E)
- NO frontend, NO production deployment
- Strict tenant isolation via `TenantContext`

---

## Implementation Details

### API Endpoints

#### Service Catalog
```
POST   /salons/{salon_id}/services              Create service
GET    /salons/{salon_id}/services              List services (tenant-scoped)
GET    /salons/{salon_id}/services/{service_id} Get one service
PATCH  /salons/{salon_id}/services/{service_id} Update service
POST   /salons/{salon_id}/services/{service_id}/activate    Activate
POST   /salons/{salon_id}/services/{service_id}/deactivate  Deactivate
```

**Design:**
- Path salon_id is authoritative (client cannot override)
- Service lookup always validates `service_id + salon_id` (no cross-tenant leaks)
- No hard DELETE (lifecycle: active/inactive via endpoints)

### RBAC Matrix

| Action          | Owner | Manager | Staff | Suspended |
|-----------------|-------|---------|-------|-----------|
| Create service  | ✓     | ✓       | ✗ 403 | ✗ 404     |
| Read service    | ✓     | ✓       | ✓     | ✗ 404     |
| Update service  | ✓     | ✓       | ✗ 403 | ✗ 404     |
| Activate        | ✓     | ✓       | ✗ 403 | ✗ 404     |
| Deactivate      | ✓     | ✓       | ✗ 403 | ✗ 404     |

**Implementation:**
- `TenantContext.require_owner_or_manager()` for mutations
- Staff can read all services (active + inactive) for operational awareness
- Suspended memberships get 404 (Phase 1 tenant context design)

### Contract Validation

**SalonService Schema Constraints:**
- `duration_minutes > 0` (Pydantic: `gt=0`)
- `price_amount >= 0` (Pydantic: `ge=0`, DB: CHECK constraint)
- `currency` defaults to `"IDR"` when omitted
- `description` and `category` are optional
- `salon_id` from path (client cannot spoof)

**Validation Results:**
- Zero/negative duration → 422
- Negative price → 422
- Client-provided `salon_id` in body → ignored (path wins)

### Tenant Isolation

**Cross-Tenant Security:**
- Service lookup requires BOTH `service_id` AND `salon_id` match
- Tenant B querying Tenant A's service under Tenant B's path → 404
- Tenant B querying Tenant A's path directly → 404 (no membership)
- Service list endpoint strictly `WHERE salon_id = tenant.salon.id`

**Test Coverage:**
- Cross-tenant GET (wrong path) → 404
- Cross-tenant GET (correct service_id, wrong tenant) → 404
- Service list never leaks cross-tenant data

### Decimal Price Handling

**Implementation:**
- ORM: `Numeric(12, 2)` → Python `Decimal`
- Pydantic schema: `Decimal` with `decimal_places=2`
- JSON serialization: string `"75000.00"` (not float)
- Test verifies DB storage: `saved.price_amount == Decimal("75000.00")`

---

## Test Suite

### P2-B Tests (12 new)
1. `test_owner_creates_service_with_contract_defaults` — create with minimal fields, verify defaults
2. `test_manager_creates_service_with_optional_fields` — create with all optional fields
3. `test_staff_cannot_create_service` — staff create → 403
4. `test_owner_and_manager_can_update_service` — owner + manager PATCH succeeds
5. `test_staff_cannot_update_service` — staff PATCH → 403
6. `test_owner_and_manager_activate_deactivate_lifecycle` — activate/deactivate by owner+manager
7. `test_staff_cannot_activate_or_deactivate` — staff lifecycle mutations → 403
8. `test_staff_can_read_service_and_list` — staff GET/list succeeds
9. `test_list_and_get_cross_tenant_isolation` — comprehensive cross-tenant 404 tests
10. `test_suspended_membership_denied` — suspended user → 404
11. `test_invalid_duration_and_negative_price_rejected` — contract validation → 422
12. `test_client_cannot_override_salon_id` — client-provided salon_id ignored

### Full Suite Results
```
144 passed, 20 warnings in 45.44s
```

**Breakdown:**
- Phase 1 + P2-A tests: 129 (unchanged, no regression)
- P2-B tests: 12 (original)
- P2-B audit remediation tests: 3 (NULL semantics + oversized Decimal)
- Total: 144 PASS

**Quality Gates:**
- Ruff: All checks passed
- Ruff format: 52 files formatted
- Black: Available (24.10.0)

---

## Files Modified

### New Files
- `apps/api/app/routers/service.py` — Service Catalog router (6 endpoints)
- `apps/api/app/schemas/service.py` — Request/Response schemas
- `apps/api/app/services/service_catalog.py` — Business logic layer
- `apps/api/tests/test_service_catalog.py` — 12 comprehensive tests

### Modified Files
- `apps/api/app/main.py` — Registered service router
- `docs/agent/HERMES_HANDOFF.md` — Updated status to P2-B COMPLETED

---

## Security & Design Decisions

### Tenant Authority
- **Path-authoritative salon_id:** `POST /salons/{A}/services` with `{"salon_id": "B"}` in body → service created under salon A (path wins).
- **Lookup enforcement:** Every service GET/PATCH/activate/deactivate validates `service.salon_id == tenant.salon.id`.
- **Cross-tenant hiding:** Querying another tenant's service returns 404 (not 403) per Phase 1 design.

### RBAC Enforcement
- **Mutation permission:** `require_owner_or_manager()` blocks staff from create/update/activate/deactivate.
- **Read permission:** All active membership roles (owner/manager/staff) can read services.
- **Suspended blocking:** Suspended memberships fail at `get_tenant_context` (404 before RBAC).

### No Hard Delete
- **Lifecycle:** Services are activated/deactivated, not deleted.
- **Rationale:** Preserve booking/audit history (future P2-F+ booking engine).
- **Implementation:** Explicit `/activate` and `/deactivate` endpoints (not PATCH `is_active`).

### Optional Fields
- **description:** nullable, no default
- **category:** nullable, no default (taxonomy deferred to owner decision)
- **currency:** defaults to `"IDR"`, overridable per service

---

## Verification Steps

### Pre-Commit Checks
```bash
# All tests pass
pytest tests/ -q
# 141 passed, 16 warnings in 43.10s

# Lint clean
ruff check .
# All checks passed!

# Format clean
ruff format --check .
# 53 files already formatted
```

### Manual Verification
- Service creation by owner/manager: ✓
- Service creation by staff: ✓ (403)
- Cross-tenant isolation: ✓ (404)
- Suspended membership: ✓ (404)
- Contract validation: ✓ (422)
- Decimal serialization: ✓ (string in JSON)
- Phase 1 regression: ✓ (no failures)

---

## Next Steps

**Immediate:**
- Commit P2-B implementation
- Push to remote `feature/phase-2-salon-operations`
- Request audit

**After P2-B Audit PASS:**
- P2-C: Staff Profile + Staff-Service Assignment API
- P2-D: Weekly Availability API
- P2-E: Customer Records API

**Out of Scope (Future):**
- Booking engine (Phase 2 later / Phase 3)
- Payment/POS (Phase 3+)
- Frontend (separate track)
- Production deployment (after full Phase 2)

---

## Git Status

**Branch:** feature/phase-2-salon-operations  
**Current HEAD:** 50369922eb6c7575dc7d7907565ad5cd7dc627e6  
**Working Tree:** Modified (P2-B audit remediation in progress)

**Modified Files (Audit Remediation):**
- `apps/api/app/schemas/service.py` — Added max_digits=12 to price validation
- `apps/api/app/services/service_catalog.py` — Fixed NULL semantics (nullable vs required fields)
- `apps/api/app/routers/service.py` — ValueError → HTTPException 422 for null rejection
- `apps/api/tests/test_service_catalog.py` — Added 3 regression tests
- `docs/agent/HERMES_HANDOFF.md` — Updated remote HEAD and availability wording

**Pending Commit:**
```
fix(phase2): P2-B audit remediation - NULL semantics + Decimal validation

- PATCH NULL semantics: nullable fields (description, category) clear with explicit null
- Non-nullable fields (name, duration, price, currency) reject null with 422
- Added max_digits=12 to price validation (consistency with DB Numeric(12,2))
- 3 new regression tests: clear nullable, reject null non-nullable, oversized Decimal
- 144 total tests PASS (no regression)
```

---

## Checklist

- [x] Owner create service
- [x] Manager create service
- [x] Staff create → 403
- [x] Owner/Manager update
- [x] Staff update → 403
- [x] Owner/Manager activate/deactivate
- [x] Staff mutation → 403
- [x] Staff read service → success
- [x] List tenant-scoped
- [x] Get service
- [x] Cross-tenant service → 404
- [x] Suspended membership denied
- [x] Invalid duration rejected
- [x] Negative price rejected
- [x] Omitted currency → IDR
- [x] Optional category accepted
- [x] Optional description accepted
- [x] Decimal price serialization consistent
- [x] Inactive/active lifecycle
- [x] Phase 1 regression tests PASS
- [x] Ruff clean
- [x] Format clean
- [x] HERMES_HANDOFF updated

**P2-B COMPLETION: VERIFIED ✓**

---

**Report Path:** `/home/ubuntu/salon-saas/docs/reports/phase2-p2b-completion-report.md`
