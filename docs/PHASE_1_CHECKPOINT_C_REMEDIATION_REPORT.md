# Phase 1 — Checkpoint C Final Remediation Report

Tanggal: 2026-09-30  
Status: GREEN — menunggu audit GitHub  
Branch: `feature/phase-1-auth-tenancy`  
Baseline audit pertama: `4fbcd04`  
Baseline audit kedua: `525a349`  

---

## Ringkasan Eksekutif

Remediation Checkpoint C telah selesai dan diverifikasi GREEN sesuai seluruh requirement Auditor C-1 sampai C-6.

**Commit final:** (akan diisi setelah push)  
**Test results:** 26/26 remediation tests PASS, 62/62 full backend suite PASS  
**Lint:** Ruff + Black PASS  

---

## C-1 — Member List RBAC

**Kebutuhan Auditor:**
- OWNER boleh melihat semua membership.
- MANAGER boleh melihat semua membership.
- STAFF tidak boleh mendapat akses administrasi membership.
- Policy harus centralized, tidak berupa role check tersebar.

**Implementasi:**
- Ditambahkan `apps/api/app/core/rbac.py` sebagai policy terpusat.
- `Permission.VIEW_MEMBERS` hanya diberikan kepada `owner` dan `manager`.
- `TenantContext.require_permission()` mendelegasikan keputusan ke `RBACPolicy`.
- `GET /salons/{salon_id}/members` wajib meminta `Permission.VIEW_MEMBERS`.
- STAFF yang merupakan active membership pada salon yang sama menerima `403 Permission denied`.

**Bukti test:**
- `test_owner_can_list_members` — PASS
- `test_manager_can_list_members` — PASS
- `test_staff_cannot_list_members` — PASS

---

## C-2 — Manager Mengelola STAFF Saja

**Kebutuhan Auditor:**
- OWNER dapat mengelola MANAGER dan STAFF, namun tidak dapat mengubah OWNER.
- MANAGER hanya dapat mengelola STAFF.
- MANAGER tidak dapat mengelola OWNER/MANAGER atau menaikkan STAFF menjadi MANAGER.
- STAFF tidak memiliki membership-administration permission.

**Implementasi:**
- `RBACPolicy.require_member_mutation(actor_role, target_role, requested_role)` menjadi satu-satunya policy target-aware untuk PATCH/DELETE membership.
- Matrix eksplisit:
  - OWNER → MANAGER/STAFF: diizinkan.
  - OWNER → OWNER: ditolak `403`.
  - MANAGER → STAFF dengan role tetap `staff` atau suspend: diizinkan.
  - MANAGER → STAFF menjadi `manager`: ditolak `403`.
  - MANAGER → MANAGER/OWNER: ditolak `403`.
  - STAFF → siapa pun: ditolak `403`.
- PATCH dan DELETE endpoint menjalankan policy tersebut setelah resource diverifikasi milik salon pada URL.

**Bukti test:**
- `test_manager_can_demote_staff_only` — PASS
- `test_manager_cannot_promote_staff_to_manager` — PASS
- `test_manager_cannot_manage_manager` — PASS
- `test_cannot_update_owner_role` — PASS (regression)
- `test_remove_member_as_owner` — PASS (regression)

---

## C-3 — Cross-Tenant Resource Hiding

**Kebutuhan Auditor:**
- Pengguna terautentikasi tanpa active membership pada tenant target harus menerima `404`, bukan `403`.
- `403` digunakan apabila user memang menjadi member namun tidak mempunyai permission operasi.
- Respons tidak boleh mengonfirmasi keberadaan tenant-scoped resource kepada non-member.

**Implementasi:**
- `get_tenant_context()` memuat salon dan membership tanpa menerapkan status di query awal.
- Salon tidak ada atau user tidak mempunyai membership → `404 {"detail":"Salon not found"}`.
- Membership ada tetapi tidak aktif/suspended → `404` (diperluas di C-5).
- User active member tetapi role tidak memiliki permission → `403 Permission denied` dari `RBACPolicy`.

**Bukti test:**
- `test_non_member_gets_404_for_other_salon` — PASS
- `test_cannot_access_other_salon` — PASS setelah assertion lama direkonsiliasi dari `403` ke kontrak Auditor `404`.
- `test_staff_cannot_list_members` — PASS; membuktikan user member aktif dengan role tidak cukup mendapat `403`.

---

## C-4 — Salon Slug Opsional dan Aman

**Kebutuhan Auditor:**
- `name` wajib; `slug` opsional.
- Tanpa slug, sistem membuat slug deterministik, lowercase, URL-safe, dan globally unique.
- Explicit slug dinormalisasi/divalidasi dan reserved slug ditolak.
- Uniqueness tetap diputuskan database sebagai authority terakhir.

**Implementasi:**
- `SalonCreateRequest.slug` diubah menjadi `str | None`.
- Explicit slug dinormalisasi dengan `strip().lower()` dan divalidasi pattern URL-safe existing.
- Protected route/slugs: `admin`, `api`, `auth`, `docs`, `health`, `me`, `salons`.
- `generate_unique_salon_slug()` menghasilkan base dari nama menggunakan translasi URL-safe dan collision suffix deterministik `-2`, `-3`, dst.
- Jika hasil nama kosong, fallback `salon`; jika basis reserved, diberi suffix `-salon`.
- Kolom/index unique PostgreSQL pada `salons.slug` tetap menjadi final authority untuk race/concurrency collision; endpoint mengembalikan `400` bila database melaporkan collision explicit.

**Bukti test:**
- `test_create_salon_success` — PASS (explicit slug regression)
- `test_create_salon_without_slug_generates_safe_unique_slug` — PASS
  - `Beauty & Wellness Studio` → `beauty-wellness-studio`
  - collision berikutnya → `beauty-wellness-studio-2`
- `test_create_salon_duplicate_slug` — PASS
- `test_reserved_slug_is_rejected[admin|api|auth|docs|health|me|salons]` — PASS untuk semua 7 reserved slugs.
- `test_invalid_explicit_slug_is_rejected[...]` — PASS untuk spasi, prefix hyphen, panjang kurang, dan underscore.

---

## C-5 — Suspended Membership Tidak Mengonfirmasi Tenant Access

**Kebutuhan Auditor:**
- User yang tidak memiliki ACTIVE membership pada tenant target tidak boleh memperoleh tenant context.
- Salon tidak ada → 404
- User tidak mempunyai membership → 404
- Membership suspended/inactive → 404
- Active membership tetapi role tidak cukup → 403

**Implementasi:**
- `get_tenant_context()` diperbaiki untuk menggabungkan check non-member dan suspended dalam satu kondisi 404.
- Response yang sama `"Salon not found"` untuk non-member dan suspended member agar suspended membership tidak menjadi side-channel konfirmasi hubungan user-tenant.

**Bukti test:**
- `test_suspended_member_gets_same_404_as_non_member` — PASS
- `test_non_member_gets_404_for_other_salon` — PASS (existing)
- `test_staff_cannot_list_members` — PASS (active member insufficient permission → 403)

---

## C-6 — Membership Suspension Lifecycle

**Kebutuhan Auditor:**
- OWNER dapat suspend/remove MANAGER dan STAFF, tidak dapat mutate OWNER.
- MANAGER dapat suspend/remove STAFF, tidak dapat suspend/remove MANAGER atau OWNER.
- STAFF tidak dapat melakukan membership administration.
- Implement minimal membership-status administration menggunakan centralized target-aware RBAC policy yang sama.

**Implementasi:**
- Ditambahkan `MemberStatusUpdateRequest` schema dengan pattern `^(active|suspended)$`.
- Ditambahkan `update_member_status()` service layer function yang enforce non-owner constraint.
- PATCH endpoint `/salons/{salon_id}/members/{membership_id}` menerima union payload `MemberRoleUpdateRequest | MemberStatusUpdateRequest`.
- Policy `RBACPolicy.require_member_mutation()` digunakan untuk validasi RBAC sebelum status mutation (tanpa `requested_role` parameter untuk suspend/activate).
- Cross-tenant membership ID tetap return 404.

**Bukti test:**
- `test_manager_can_suspend_staff` — PASS (manager suspend staff → success, DB verify suspended)
- `test_manager_cannot_suspend_manager` — PASS (manager suspend manager → 403)
- `test_staff_cannot_suspend_staff` — PASS (staff suspend staff → 403)
- `test_owner_can_suspend_manager` — PASS (owner suspend manager → success)
- `test_owner_cannot_suspend_owner` — PASS (owner suspend owner → 403)
- `test_cross_tenant_membership_id_is_hidden` — PASS (cross-tenant status mutation → 404)

---

## File yang Diubah

**Remediation pertama (C-1 sampai C-4):**
- `apps/api/app/core/rbac.py` — Policy RBAC centralized dan target-aware.
- `apps/api/app/core/tenant.py` — Tenant context dengan resource hiding cross-tenant (`404`) dan permission delegation.
- `apps/api/app/routers/tenant.py` — Enforcement `VIEW_MEMBERS` dan policy mutation centralized.
- `apps/api/app/schemas/tenant.py` — Slug opsional, normalisasi explicit slug, reserved slug validation (7 reserved slugs).
- `apps/api/app/services/tenant.py` — Generator slug deterministic/collision-safe.
- `apps/api/tests/test_checkpoint_c_remediation.py` — 17 test khusus remediation Auditor pertama.
- `apps/api/tests/test_tenant_rbac.py` — Existing cross-tenant expectation direkonsiliasi dengan kontrak `404` Auditor.

**Remediation kedua (C-5 dan C-6):**
- `apps/api/app/core/tenant.py` — Suspended membership diperlakukan sama dengan non-member (404).
- `apps/api/app/schemas/tenant.py` — Ditambahkan `MemberStatusUpdateRequest`.
- `apps/api/app/services/tenant.py` — Ditambahkan `update_member_status()`.
- `apps/api/app/routers/tenant.py` — PATCH endpoint menerima union `MemberRoleUpdateRequest | MemberStatusUpdateRequest`.
- `apps/api/tests/test_checkpoint_c_remediation.py` — Ditambahkan 9 test C-5 dan C-6 (total 26 test).

---

## Validasi Dilakukan

**Remediation pertama:**
1. RED sebelum implementasi: 8 test FAIL tepat pada gap C-1 sampai C-4.
2. GREEN remediation: 17 passed.
3. Full backend suite: 53 passed.
4. Ruff + Black: PASS.

**Remediation kedua:**
1. RED sebelum implementasi C-5 & C-6: suspended member test belum ada, status mutation endpoint belum ada.
2. GREEN remediation: 26 passed.
3. Full backend suite: 62 passed.
4. Ruff + Black: PASS.

---

## Catatan Non-Blocking

Pytest menampilkan warning dependency `StarletteDeprecationWarning` dari `fastapi.testclient` dan beberapa `SAWarning` fixture transaksi pada test lama. Tidak ada test failure atau lint/format failure. Warning tersebut bukan bagian remediation C, namun perlu dicatat sebagai technical-debt test infrastructure sebelum final Phase 1 sign-off.

---

## Status Engineering

**SELESAI:**
- Remediation C-1: member list RBAC — ✅
- Remediation C-2: manager manage staff only — ✅
- Remediation C-3: cross-tenant 404 hiding — ✅
- Remediation C-4: optional slug + reserved slug protection — ✅
- Remediation C-5: suspended membership 404 — ✅
- Remediation C-6: membership suspension lifecycle — ✅

**Test Coverage:**
- Remediation tests: 26/26 PASS
- Full backend suite: 62/62 PASS
- Lint: Ruff PASS, Black PASS

**Next:**
- Commit remediation C final.
- Push ke GitHub.
- Auditor review dari GitHub.
- Jika Auditor approve, lanjut Checkpoint D.

**Out of scope:**
- Frontend/BFF tetap ownership Muse.ai.
- Phase 2 belum dimulai.
