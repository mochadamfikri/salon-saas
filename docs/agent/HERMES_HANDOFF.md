# Hermes Handoff

## Current Branch
feature/phase-2-salon-operations

## Phase 1 Status
Checkpoint A-D PASS.
Checkpoint E belum selesai.

## Current Task
Phase 2 P2-A — database schema, migration, dan domain model Salon Operations Core.

## Scope P2-A
- Salon Service
- Staff Profile
- Staff-Service Assignment
- Staff Weekly Availability
- Salon Customer

## Rules
- semua tenant-scoped
- UUID
- timestamps
- PostgreSQL constraints
- gunakan TenantContext/RBAC Phase 1
- jangan booking engine dulu
- jangan payment/POS/inventory/payroll/attendance
- jangan frontend
- jangan production

## Next Action
Audit model/migration Phase 1 yang sudah ada, lalu implement P2-A.

## Last Commit
SHA: 5171a18
Message: docs: update remediation report with actual commit SHA
