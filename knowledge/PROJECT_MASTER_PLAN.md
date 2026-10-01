# Salon SaaS — Project Master Plan

This is the high-level roadmap. Detailed execution rules live in per-phase specs.

## Phase 0 — Foundation
**Status: FINAL PASS / COMPLETE**

Repository/monorepo, Next.js and FastAPI foundations, PostgreSQL 16, Redis 7, Alembic, tests/lint/build, Docker development infrastructure, environment boundaries, and architecture documentation.

## Phase 1 — Authentication & Multi-Tenant Identity
**Status: implemented baseline; core backend checkpoints A-D passed; frontend Phase 1 accepted. Final integration/checkpoint-E closure remains a separate project acceptance item.**

Core domains:
- global user identity;
- login/register/session;
- rotating refresh tokens;
- salon creation;
- memberships/roles;
- invitations;
- tenant context/isolation;
- frontend auth/BFF/session handling.

## Phase 2 — Salon Operations Foundation
**Status: IN PROGRESS**

Detailed spec: `knowledge/phases/PHASE2_MASTER_SPEC.md`

Checkpoints:
- P2-A Domain Foundation
- P2-B Service Catalog
- P2-C Staff Profile + Staff-Service Assignment
- P2-D Weekly Availability
- P2-E Customer Records
- corresponding frontend UI/integration

Purpose: stable salon operational primitives required by future booking.

## Phase 3 — Booking / Appointment Engine
**Status: PLANNED — detailed business contract not yet approved**

Expected dependencies:
- auth/tenant baseline;
- service catalog;
- staff profiles/service capability;
- weekly availability;
- customer records.

Expected topics needing Owner-approved Phase 3 spec:
- booking creation;
- customer/service/staff linkage;
- staff capability validation;
- availability validation;
- booking overlap/concurrency;
- lifecycle/state machine;
- reschedule/cancel rules;
- duration/price snapshots;
- timezone rules.

Do not implement Phase 3 until its master spec is approved.

## Future Product Domains — Sequencing Not Yet Approved
Existing architecture identifies future domains, but they are **not assigned phase numbers yet**. Owner approval is required before they become `PHASE4_MASTER_SPEC.md`, `PHASE5_MASTER_SPEC.md`, etc.

Known future domains:
- branch/multi-location operations;
- products/inventory;
- POS;
- invoices/payments/transactions;
- staff commissions/payroll/attendance;
- reports/analytics;
- WhatsApp/Telegram and other notifications;
- public storefront/customer portal;
- platform administration;
- loyalty/packages/subscriptions if approved later.

Agents must not infer phase ordering from this backlog.
