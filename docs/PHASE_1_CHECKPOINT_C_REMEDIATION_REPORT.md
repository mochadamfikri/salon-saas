# Phase 1 — Checkpoint C Remediation Report

Tanggal: 2026-09-30
Status: GREEN — menunggu audit GitHub
Branch: `feature/phase-1-auth-tenancy`
Baseline audited: `4fbcd04`

## Tujuan

Dokumen ini mencatat remediation yang diminta Auditor atas Checkpoint C. Checkpoint C tidak dinyatakan final PASS oleh engineering sebelum commit ini diverifikasi Auditor dari GitHub.

## C-1 — Member List RBAC

Kebutuhan Auditor:

- OWNER boleh melihat semua membership.
- MANAGER boleh melihat semua membership.
- STAFF tidak boleh mendapat akses administrasi membership.
- Policy harus centralized, tidak berupa role check tersebar.

Implementasi:

- Ditambahkan `apps/api/app/core/rbac.py` sebagai policy terpusat.
- `Permission.VIEW_MEMBERS` hanya diberikan kepada `owner` dan `manager`.
- `TenantContext.require_permission()` mendelegasikan keputusan ke `RBACPolicy`.
- `GET /salons/{salon_id}/members` wajib meminta `Permission.VIEW_MEMBERS`.
- STAFF yang merupakan active membership pada salon yang sama menerima `403 Permission denied`.

Bukti test:

- `test_owner_can_list_members` — PASS
- `test_manager_can_list_members` — PASS
- `test_staff_cannot_list_members` — PASS

## C-2 — Manager Mengelola STAFF Saja

Kebutuhan Auditor:

- OWNER dapat mengelola MANAGER dan STAFF, namun tidak dapat mengubah OWNER.
- MANAGER hanya dapat mengelola STAFF.
- MANAGER tidak dapat mengelola OWNER/MANAGER atau menaikkan STAFF menjadi MANAGER.
- STAFF tidak memiliki membership-administration permission.

Implementasi:

- `RBACPolicy.require_member_mutation(actor_role, target_role, requested_role)` menjadi satu-satunya policy target-aware untuk PATCH/DELETE membership.
- Matrix eksplisit:
  - OWNER → MANAGER/STAFF: diizinkan.
  - OWNER → OWNER: ditolak `403`.
  - MANAGER → STAFF dengan role tetap `staff`: diizinkan.
  - MANAGER → STAFF menjadi `manager`: ditolak `403`.
  - MANAGER → MANAGER/OWNER: ditolak `403`.
  - STAFF → siapa pun: ditolak `403`.
- PATCH dan DELETE endpoint menjalankan policy tersebut setelah resource diverifikasi milik salon pada URL.

Bukti test:

- `test_manager_can_demote_staff_only` — PASS
- `test_manager_cannot_promote_staff_to_manager` — PASS
- `test_manager_cannot_manage_manager` — PASS
- `test_cannot_update_owner_role` — PASS (regression)
- `test_remove_member_as_owner` — PASS (regression)

## C-3 — Cross-Tenant Resource Hiding

Kebutuhan Auditor:

- Pengguna terautentikasi tanpa active membership pada tenant target harus menerima `404`, bukan `403`.
- `403` digunakan apabila user memang menjadi member namun tidak mempunyai permission operasi.
- Respons tidak boleh mengonfirmasi keberadaan tenant-scoped resource kepada non-member.

Implementasi:

- `get_tenant_context()` memuat salon dan membership tanpa menerapkan status di query awal.
- Salon tidak ada atau user tidak mempunyai membership → `404 {"detail":"Salon not found"}`.
- Membership ada tetapi tidak aktif/suspended → `403`.
- User active member tetapi role tidak memiliki permission → `403 Permission denied` dari `RBACPolicy`.

Bukti test:

- `test_non_member_gets_404_for_other_salon` — PASS
- `test_cannot_access_other_salon` — PASS setelah assertion lama direkonsiliasi dari `403` ke kontrak Auditor `404`.
- `test_staff_cannot_list_members` — PASS; membuktikan user member aktif dengan role tidak cukup mendapat `403`.

## C-4 — Salon Slug Opsional dan Aman

Kebutuhan Auditor:

- `name` wajib; `slug` opsional.
- Tanpa slug, sistem membuat slug deterministik, lowercase, URL-safe, dan globally unique.
- Explicit slug dinormalisasi/divalidasi dan reserved slug ditolak.
- Uniqueness tetap diputuskan database sebagai authority terakhir.

Implementasi:

- `SalonCreateRequest.slug` diubah menjadi `str | None`.
- Explicit slug dinormalisasi dengan `strip().lower()` dan divalidasi pattern URL-safe existing.
- Protected route/slugs: `admin`, `api`, `auth`, `docs`, `health`, `me`, `salons`.
- `generate_unique_salon_slug()` menghasilkan base dari nama menggunakan translasi URL-safe dan collision suffix deterministik `-2`, `-3`, dst.
- Jika hasil nama kosong, fallback `salon`; jika basis reserved, diberi suffix `-salon`.
- Kolom/index unique PostgreSQL pada `salons.slug` tetap menjadi final authority untuk race/concurrency collision; endpoint mengembalikan `400` bila database melaporkan collision explicit.

Bukti test:

- `test_create_salon_success` — PASS (explicit slug regression)
- `test_create_salon_without_slug_generates_safe_unique_slug` — PASS
  - `Beauty & Wellness Studio` → `beauty-wellness-studio`
  - collision berikutnya → `beauty-wellness-studio-2`
- `test_create_salon_duplicate_slug` — PASS
- `test_reserved_slug_is_rejected[...]` — PASS untuk `admin`, `api`, `auth`, `me`, dan `salons`.
- `test_invalid_explicit_slug_is_rejected[...]` — PASS untuk spasi, prefix hyphen, panjang kurang, dan underscore.

## File yang Diubah

- `apps/api/app/core/rbac.py`
  - Policy RBAC centralized dan target-aware.
- `apps/api/app/core/tenant.py`
  - Tenant context dengan resource hiding cross-tenant (`404`) dan permission delegation.
- `apps/api/app/routers/tenant.py`
  - Enforcement `VIEW_MEMBERS` dan policy mutation centralized.
- `apps/api/app/schemas/tenant.py`
  - Slug opsional, normalisasi explicit slug, reserved slug validation.
- `apps/api/app/services/tenant.py`
  - Generator slug deterministic/collision-safe.
- `apps/api/tests/test_checkpoint_c_remediation.py`
  - 17 test khusus remediation Auditor.
- `apps/api/tests/test_tenant_rbac.py`
  - Existing cross-tenant expectation direkonsiliasi dengan kontrak `404` Auditor.

## Validasi Dilakukan

1. RED sebelum implementasi:

   `pytest tests/test_checkpoint_c_remediation.py -v --tb=short`

   Hasil awal: 8 test FAIL tepat pada gap C-1 sampai C-4 (staff listing, manager staff mutation, cross-tenant 403, slug mandatory, reserved slug diterima).

2. GREEN remediation:

   `pytest tests/test_checkpoint_c_remediation.py -v`

   Hasil: `17 passed`.

3. Full backend suite:

   `pytest tests/ -q`

   Hasil: `53 passed`.

4. Static quality gates:

   `ruff check .`

   Hasil: `All checks passed!`

   `black --check .`

   Hasil: `33 files would be left unchanged.`

## Catatan Non-Blocking

Pytest masih menampilkan warning dependency `StarletteDeprecationWarning` dari `fastapi.testclient`/versi dependency dan beberapa `SAWarning` fixture transaksi pada test lama. Tidak ada test failure atau lint/format failure. Warning tersebut bukan bagian remediation C, namun perlu dicatat sebagai technical-debt test infrastructure sebelum final Phase 1 sign-off bila masih muncul.

## Status Engineering

- Remediation code dan audit report ini perlu di-commit dan di-push setelah review diff akhir.
- Setelah push, Auditor diminta memeriksa commit SHA dan report ini dari GitHub.
- Checkpoint D belum dimulai.
- Tidak ada frontend/BFF yang diimplementasikan Hermes; frontend tetap ownership Muse.ai.
