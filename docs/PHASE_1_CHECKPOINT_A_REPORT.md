# CHECKPOINT A REPORT — SALON SAAS PHASE 1
Tanggal: 2026-09-29 UTC  
Branch: `feature/phase-1-auth-tenancy`  
Base: `origin/develop` (`524977d`)  
HEAD: `40ca3e0`  
Repository: `mochadamfikri/salon-saas` (Public)

---

## Ringkasan Eksekutif Checkpoint A

Checkpoint A (P1-001 hingga P1-004) telah diselesaikan secara penuh dengan status **PASS**.
Fokus checkpoint ini adalah keamanan repositori publik, spesifikasi Phase 1, model ORM untuk 6 entitas utama, migrasi Alembic yang tervalidasi bolak-balik (upgrade/downgrade/re-upgrade/clean DB), dependency database terpusat, dan pengujian constraint database.

Tidak ada endpoint authentication, JWT flow, atau fitur operasional bisnis (booking/payment) yang dibuat pada checkpoint ini sesuai batasan scope.

---

## Status Task Checkpoint A

| Task | Deskripsi | Status | Bukti / Catatan |
|---|---|---|---|
| **P1-001** | Public repo security pre-flight & docs reconciliation | **PASS** | Scan secret bersih, `.env` tidak pernah di-commit, docs di-update |
| **P1-002** | Branch, progress doc & specification boundary | **PASS** | Branch `feature/phase-1-auth-tenancy`, spec lengkap 14 bab, progress P1-001..P1-030 |
| **P1-003** | ORM models 6 entitas & migrasi Alembic | **PASS** | 6 tabel dibuat, migrasi `20260929_0002`, validasi upgrade/downgrade/clean PASS |
| **P1-004** | Centralized DB session dependency & repository | **PASS** | `get_db()` generator di `apps/api/app/core/dependencies.py`, session lifecycle tested |

---

## Detail Pelaksanaan per Task

### P1-001 — Public Repository Security Pre-Flight & Docs Reconciliation
- **Visibilitas Repo:** Dikonfirmasi public di `https://github.com/mochadamfikri/salon-saas`.
- **Secret Scan:**
  - Riwayat commit `.env`: `git log --all -p -- .env` menghasilkan 0 baris (tidak pernah di-commit).
  - Pengecekan file berbahaya: Tidak ada `.pem`, `.key`, `id_rsa`, kredensial live.
  - Scan heuristic: 0 temuan real secret.
- **Rekonsiliasi Dokumen:**
  - `docs/PHASE_0_AUDIT_REPORT_2026-09-29.md` diperbarui menandai repo publik.
  - `docs/PROGRESS.md` baris 37 diperbarui menghapus klaim `private`.

### P1-002 — Phase 1 Branch & Specification Boundary
- **Branch:** Dibuat `feature/phase-1-auth-tenancy` dari latest `origin/develop` (`524977d`).
- **Dokumen Spesifikasi:** `docs/PHASE_1_AUTH_TENANCY.md` dibuat lengkap (bukan placeholder, ~12 KB):
  - Tujuan Phase 1 & arsitektur global identity.
  - Tenant membership & model role (`owner`, `manager`, `staff`).
  - Penegasan customer bukan tenant role.
  - Model Salon, User, Session, Password Reset, dan Undangan.
  - Kebijakan password Argon2id & dual token architecture (JWT 15m + Opaque rotating refresh).
  - Isolasi tenant, RBAC rules, task matrix P1-001 sampai P1-030.
  - Definition of Done dan Out-of-Scope.
- **Dokumen Aturan:** `docs/AGENT_RULES.md` diperbarui menandai Phase 0 completed dan mengaktifkan aturan Phase 1.
- **Progress Tracker:** `docs/PROGRESS.md` memuat seluruh 30 task Phase 1.

### P1-003 — ORM Models & Alembic Migration
- **Model ORM (`apps/api/app/models.py`):**
  1. `User`: Global identity. UUID PK, unique email (dengan normalisasi otomatis lowercase/strip), `is_active`, `is_super_admin`, tanpa kolom `salon_id` atau role tenant.
  2. `Salon`: Tenant root. UUID PK, unique slug, status constraint (`onboarding`, `active`, `suspended`), `created_by_user_id` (FK RESTRICT).
  3. `SalonMembership`: Pemegang role tenant. UUID PK, `UNIQUE(salon_id, user_id)`, role constraint (`owner`, `manager`, `staff`), status (`active`, `suspended`).
  4. `AuthSession`: Metadata session refresh rotating. UUID PK, `token_hash` unik (raw token tidak disimpan plaintext), `family_id` (deteksi reuse), `replaced_by_session_id` (FK self-referential RESTRICT), `expires_at`, `revoked_at`.
  5. `SalonInvitation`: Undangan staff/manager berbatas waktu. UUID PK, `token_hash` unik, role constraint (`manager`, `staff`), `expires_at`, `accepted_at`, `revoked_at`.
  6. `PasswordResetToken`: Token reset sekali pakai. UUID PK, `token_hash` unik, `expires_at`, `used_at`.
- **Migrasi Alembic (`20260929_0002`):**
  - File: `apps/api/migrations/versions/20260929_0002_phase_1_identity_and_tenancy_foundation.py`.
  - Revises: `20260929_0001` (Phase 0 baseline).
  - Validasi siklus migrasi:
    - Upgrade: `20260929_0001` -> `20260929_0002 (head)` (SUKSES)
    - Downgrade: `20260929_0002` -> `20260929_0001` (SUKSES)
    - Re-upgrade: `20260929_0001` -> `20260929_0002 (head)` (SUKSES)
    - Clean DB upgrade: Membuat database temporer baru, upgrade head, verifikasi 7 tabel hadir (SUKSES)

### P1-004 — Centralized DB Session Dependency
- **File:** `apps/api/app/core/dependencies.py`
- **Fungsi:** `get_db() -> Generator[Session]`
- **Karakteristik:**
  - Menyediakan session per request via FastAPI dependency injection.
  - Memastikan session selalu di-`close()` di blok `finally`.
  - Mencegah inisialisasi session manual di dalam route handler.
  - Driver sinkron Psycopg 3 + SQLAlchemy 2.0 dipertahankan sesuai ADR-012.

---

## Hasil Pengujian (Automated Tests)

Semua 10 test backend lulus (`pytest -v`):
1. `tests/test_database.py::test_database_connection_uses_development_database` **PASSED**
2. `tests/test_health.py::test_health_endpoint_returns_service_status` **PASSED**
3. `tests/test_migrations.py::test_migrations_upgrade_configured_development_database_to_head` **PASSED**
4. `tests/test_migrations.py::test_migrations_upgrade_clean_database_to_head` **PASSED**
5. `tests/test_phase1_schema.py::test_phase1_tables_exist` **PASSED**
6. `tests/test_phase1_schema.py::test_get_db_session_dependency` **PASSED**
7. `tests/test_phase1_schema.py::test_user_email_is_normalized_and_unique_case_insensitively` **PASSED**
8. `tests/test_phase1_schema.py::test_salon_slug_uniqueness` **PASSED**
9. `tests/test_phase1_schema.py::test_salon_membership_unique_salon_user` **PASSED**
10. `tests/test_phase1_schema.py::test_foreign_key_restricts_deletion` **PASSED**

Pengujian frontend (`apps/web`):
- `npm test`: 4 passed (Vitest)
- `npm run lint`: ESLint clean (exit code 0)
- `npm run build`: Next.js 16.3.7 compiled successfully

Linting & Formatting backend:
- `ruff check .`: All checks passed!
- `black --check .`: All done! 14 files unchanged.

---

## Log Git Commit Checkpoint A

Semua commit terfokus dan telah di-push ke remote branch:
- `64a7817` - docs(phase1): reconcile private->public references in Phase 0 docs
- `576e325` - docs(phase1): add Phase 1 specification and update agent rules
- `a2c2bad` - feat(phase1): implement Phase 1 ORM models and DB dependency
- `d91e8b4` - feat(phase1): add Phase 1 migration 20260929_0002
- `707447a` - test(phase1): add schema constraint and migration tests
- `40ca3e0` - feat(phase1): add email normalization validator to User model

---

## Keputusan Arsitektur & Catatan Teknis

1. **Email Normalization:** Menambahkan validator `@validates("email")` di model `User` untuk otomatis melakukan `strip().lower()` sebelum data disimpan, menjamin keunikan email case-insensitive di level aplikasi dan DB.
2. **Penghapusan Berantai (Cascade):** Semua relasi foreign key dari entitas anak ke entitas induk menggunakan `ondelete="RESTRICT"` untuk mencegah penghapusan data secara tidak sengaja (anti-accidental data loss).
3. **Session Lifecycle:** `get_db()` membungkus session dalam generator `try...finally` agar koneksi database selalu dikembalikan ke pool SQLAlchemy setelah request lifecycle selesai.

---

## Kesimpulan & Langkah Selanjutnya

Checkpoint A telah selesai 100% dan terverifikasi. Sesuai instruksi, pekerjaan dihentikan di sini untuk menunggu audit dan persetujuan lanjut ke **Checkpoint B (P1-005 hingga P1-013: Authentication Core, Argon2id, JWT, Refresh Token & Auth Endpoints)**.
