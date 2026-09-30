# Phase 2 P2-C Completion Report

**Checkpoint:** P2-C Staff Profile + Staff-Service Assignment API  
**Branch:** feature/phase-2-salon-operations  
**Completion Date:** 2026-09-30  
**Status:** ✅ COMPLETED - AWAITING AUDIT

---

## Executive Summary

P2-C implements Staff Profile management and Staff-Service Assignment API with full RBAC enforcement and cross-tenant isolation. All 176 tests PASS (32 new P2-C tests + 144 regression). Full compliance with owner business decision contract.

---

## Deliverables

### 1. Staff Profile CRUD API

**Endpoints:**
```
POST   /salons/{salon_id}/staff-profiles
GET    /salons/{salon_id}/staff-profiles
GET    /salons/{salon_id}/staff-profiles/{staff_profile_id}
PATCH  /salons/{salon_id}/staff-profiles/{staff_profile_id}
POST   /salons/{salon_id}/staff-profiles/{staff_profile_id}/toggle-bookable
```

**Business Rules Implemented:**
- ✅ Explicit provisioning (NOT auto-created with membership)
- ✅ One membership → max one profile (409 on duplicate)
- ✅ Owner/Manager/Staff roles can all have profiles (service providers)
- ✅ Profile creation requires active membership from same salon
- ✅ No hard delete (use `is_bookable=false` for operational control)
- ✅ Suspended membership rejected (422)
- ✅ Cross-salon membership rejected (404)

### 2. Staff-Service Assignment API

**Endpoints:**
```
POST   /salons/{salon_id}/staff-profiles/{staff_profile_id}/services/{service_id}
GET    /salons/{salon_id}/staff-profiles/{staff_profile_id}/services
DELETE /salons/{salon_id}/staff-profiles/{staff_profile_id}/services/{service_id}
```

**Cross-Salon Invariant Enforcement:**
```
staff_profile.membership.salon_id == service.salon_id == tenant.salon.id
```

Validated at service layer BEFORE insert. Cross-salon attempts return 404 (no tenant leak).

### 3. RBAC Matrix

#### Staff Profile Operations

| Action                | Owner | Manager | Staff |
|-----------------------|-------|---------|-------|
| Create profile        | ✓     | ✓       | ✗     |
| Read/list profiles    | ✓     | ✓       | ✓     |
| Update personal fields| ✓ any | ✓ any   | ✓ own |
| Toggle is_bookable    | ✓     | ✓       | ✗     |

**Personal Fields:**
- display_name, phone, bio, photo_url
- Staff can update own profile only
- Owner/Manager can update any profile

**Operational Control:**
- `is_bookable` flag: Owner/Manager ONLY
- Immutable: `membership_id` (rejected via `extra="forbid"`)

#### Staff-Service Assignment Operations

| Action          | Owner | Manager | Staff |
|-----------------|-------|---------|-------|
| Assign service  | ✓     | ✓       | ✗     |
| Unassign service| ✓     | ✓       | ✗     |
| Read assignments| ✓     | ✓       | ✓     |

Staff cannot self-assign/unassign (operational/business control, not personal preference).

---

## Technical Implementation

### Files Created

1. **app/services/staff_profile.py** (6,674 bytes)
   - create_staff_profile()
   - list_staff_profiles()
   - get_staff_profile()
   - update_staff_profile()
   - toggle_staff_bookable()
   - create_staff_service_assignment()
   - list_staff_service_assignments()
   - get_staff_service_assignment()
   - delete_staff_service_assignment()

2. **app/schemas/staff_profile.py** (1,676 bytes)
   - StaffProfileCreateRequest
   - StaffProfileUpdateRequest (extra="forbid")
   - StaffProfileResponse
   - StaffProfileToggleBookableRequest
   - StaffServiceAssignmentResponse

3. **app/routers/staff_profile.py** (10,758 bytes)
   - 9 endpoints with TenantContext + RBAC guards
   - Self-profile determination via `membership.user_id == current_user.id`
   - Owner/Manager permission helpers

4. **tests/test_staff_profile.py** (34,835 bytes)
   - 32 comprehensive contract tests

### Files Modified

1. **app/main.py**
   - Added staff_profile_router

---

## Test Coverage (32 Tests - All PASS)

### Staff Profile Creation (8 tests)
- ✅ Owner creates profile for staff
- ✅ Manager creates profile
- ✅ Owner membership can have profile
- ✅ Manager membership can have profile
- ✅ Staff cannot create own profile (403)
- ✅ Duplicate membership profile → 409
- ✅ Cross-salon membership → 404
- ✅ Suspended target membership rejected (422)

### Staff Profile Read (3 tests)
- ✅ Owner can list all profiles
- ✅ Manager can read all profiles
- ✅ Staff can list same tenant profiles

### Staff Profile Update (7 tests)
- ✅ Staff can update own personal fields
- ✅ Staff cannot update another profile (403)
- ✅ Staff cannot toggle is_bookable (403)
- ✅ Owner can toggle is_bookable
- ✅ Manager can toggle is_bookable
- ✅ Nullable personal fields can be cleared (explicit null)
- ✅ Owner can update any profile personal fields
- ✅ Manager can update any profile personal fields
- ✅ membership_id cannot be changed via PATCH (422 extra field)

### Staff-Service Assignment (14 tests)
- ✅ Owner can assign service to staff
- ✅ Manager can assign service
- ✅ Staff cannot assign service (403)
- ✅ Staff cannot self-assign service (403)
- ✅ Duplicate assignment → 409
- ✅ Owner can unassign service
- ✅ Manager can unassign service
- ✅ Staff cannot unassign service (403)
- ✅ Assignment list and read (staff can read)
- ✅ Cross-salon staff profile → 404
- ✅ Cross-salon service → 404
- ✅ Service/profile tenant mismatch rejected (404)

---

## Validation Results

### Test Suite
```
176 tests PASS
32 new P2-C tests
144 Phase 1 + P2-A + P2-B regression tests
0 failures
```

### Linting
```
✅ black --check .
✅ ruff check .
✅ ruff format --check .
```

### Schema
- No migration required
- Existing P2-A schema sufficient
- All constraints enforced at service layer

---

## Business Contract Compliance

### Owner Business Decision Adherence

✅ **Profile Lifecycle**
- Explicit provisioning (not auto-created)
- Owner/Manager/Staff can all be service providers
- No hard delete (operational flag `is_bookable`)

✅ **Profile RBAC**
- Owner/Manager: full control
- Staff: read all, update own, cannot toggle is_bookable

✅ **Profile Update Scope**
- Personal fields: display_name, phone, bio, photo_url
- Self-determination via membership.user_id check
- Immutable membership_id enforced

✅ **Assignment RBAC**
- Owner/Manager ONLY (operational control)
- Staff read-only

✅ **Assignment Lifecycle**
- Simple single-resource POST/DELETE
- No bulk operations (deferred)
- Duplicate → 409

✅ **Cross-Salon Invariant**
- Enforced at service layer before insert
- All three salon_id must match
- Cross-salon attempts → 404

---

## API Contract Examples

### Create Staff Profile (Owner/Manager)
```http
POST /salons/{salon_id}/staff-profiles
Authorization: Bearer {owner_token}
Content-Type: application/json

{
  "membership_id": "uuid"
}

Response 201:
{
  "id": "uuid",
  "membership_id": "uuid",
  "display_name": null,
  "phone": null,
  "bio": null,
  "photo_url": null,
  "is_bookable": true,
  "created_at": "2026-09-30T...",
  "updated_at": "2026-09-30T..."
}
```

### Update Personal Fields (Staff own profile)
```http
PATCH /salons/{salon_id}/staff-profiles/{profile_id}
Authorization: Bearer {staff_token}
Content-Type: application/json

{
  "display_name": "John Stylist",
  "phone": "+6281234567890",
  "bio": "Expert stylist"
}

Response 200: {...}
```

### Toggle Bookable Flag (Owner/Manager only)
```http
POST /salons/{salon_id}/staff-profiles/{profile_id}/toggle-bookable
Authorization: Bearer {owner_token}
Content-Type: application/json

{
  "is_bookable": false
}

Response 200: {...}
```

### Assign Service (Owner/Manager only)
```http
POST /salons/{salon_id}/staff-profiles/{profile_id}/services/{service_id}
Authorization: Bearer {owner_token}

Response 201:
{
  "id": "uuid",
  "staff_profile_id": "uuid",
  "salon_service_id": "uuid",
  "created_at": "2026-09-30T...",
  "updated_at": "2026-09-30T..."
}
```

### List Assignments (All roles)
```http
GET /salons/{salon_id}/staff-profiles/{profile_id}/services
Authorization: Bearer {staff_token}

Response 200: [...]
```

### Unassign Service (Owner/Manager only)
```http
DELETE /salons/{salon_id}/staff-profiles/{profile_id}/services/{service_id}
Authorization: Bearer {owner_token}

Response 204 No Content
```

---

## Error Handling

| Scenario                          | Status | Detail                          |
|-----------------------------------|--------|---------------------------------|
| Staff creates profile             | 403    | Owner or manager role required  |
| Duplicate membership profile      | 409    | Membership already has profile  |
| Cross-salon membership            | 404    | Membership not found            |
| Suspended target membership       | 422    | Cannot create profile           |
| Staff updates another profile     | 403    | You can only update your own    |
| Staff toggles is_bookable         | 403    | Owner or manager role required  |
| Immutable field in PATCH          | 422    | Extra inputs not permitted      |
| Staff assigns service             | 403    | Owner or manager role required  |
| Duplicate assignment              | 409    | Assignment already exists       |
| Cross-salon profile/service       | 404    | Resource not found              |
| Profile not found                 | 404    | Staff profile not found         |
| Assignment not found              | 404    | Assignment not found            |

---

## Git History

**Commit 1:** `a7f5a3c`
```
feat(phase2): P2-C staff profile + staff-service assignment API + RBAC + tests

- StaffProfile CRUD with explicit provisioning
- Owner/Manager/Staff can all have profiles (service providers)
- Personal fields update (staff own, owner/manager any)
- is_bookable toggle (owner/manager only)
- Staff-Service Assignment with cross-salon invariant
- Assignment mutation: owner/manager only
- 30 P2-C tests + full regression PASS
```

**Commit 2:** `a38e072`
```
feat(phase2): P2-C contract hardening - immutable field validation + manager update tests

- extra="forbid" on StaffProfileUpdateRequest
- membership_id immutability enforced
- Manager RBAC update test coverage
- 32 total P2-C tests PASS
```

**Remote HEAD:** `a38e072`

---

## Branch State

```bash
Branch: feature/phase-2-salon-operations
Status: Clean working directory
Commits ahead of develop: 8
Latest commit: a38e072 (2026-09-30)
Remote: Pushed to origin
```

---

## Next Actions

**STOP - AWAITING P2-C AUDIT**

After P2-C audit PASS:
- **P2-D:** Staff Weekly Availability API
- **P2-E:** Salon Customer Records API

**DO NOT START:**
- Weekly Availability (P2-D)
- Customer Records (P2-E)
- Booking engine
- Frontend
- Production deployment
- Payment/POS/inventory/payroll/attendance

---

## Audit Checklist

- [ ] Business decision contract compliance verified
- [ ] RBAC matrix correct for all roles
- [ ] Cross-salon invariant enforced
- [ ] Immutable fields rejected
- [ ] Error responses appropriate (no tenant leak)
- [ ] Test coverage sufficient
- [ ] Nullable field semantics correct
- [ ] Self-profile determination secure
- [ ] No schema migration side effects
- [ ] Regression tests PASS

---

**Report Generated:** 2026-09-30T20:02:46Z  
**Author:** Hermes Agent (Nous Research)  
**Phase:** 2 Salon Operations - Checkpoint C  
**Baseline:** 96b289297bc7f5a0322a0467fb0d962bc2cb7e58
