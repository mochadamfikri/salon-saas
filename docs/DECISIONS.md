# Architectural Decision Record

This document tracks all significant architectural decisions made during the Salon SaaS platform development.

---

## ADR-001: Use PostgreSQL as Primary Database

**Decision:**
Use PostgreSQL as the primary database.

**Reason:**
The system has strong relational data requirements and needs transactional integrity for:
- Booking and schedule management
- Payment processing
- Invoice generation
- Stock management
- Commission calculation
- Multi-tenant relationships

PostgreSQL provides:
- ACID compliance
- Strong referential integrity
- Advanced querying capabilities
- JSON support for flexible data
- Row-level security for tenant isolation
- Proven scalability

**Alternatives Considered:**
- MongoDB: Rejected due to lack of transaction support across collections and weaker consistency guarantees for financial data

**Status:** ACCEPTED

---

## ADR-002: Use Monorepo Structure

**Decision:**
Use a monorepo structure with separate apps for web and api.

**Reason:**
- Shared code reusability (types, utilities, UI components)
- Atomic changes across frontend and backend
- Simplified dependency management
- Easier to maintain consistency
- Better for small teams

**Structure:**
```
salon-saas/
├── apps/
│   ├── web/       # Next.js frontend
│   └── api/       # FastAPI backend
├── packages/
│   ├── ui/        # Shared UI components
│   └── shared/    # Shared utilities and types
```

**Alternatives Considered:**
- Polyrepo: Rejected due to increased coordination overhead and duplicated code

**Status:** ACCEPTED

---

## ADR-003: Use FastAPI for Backend

**Decision:**
Use FastAPI (Python) for the backend API.

**Reason:**
- Modern async Python framework
- Automatic OpenAPI/Swagger documentation
- Built-in data validation with Pydantic
- High performance (comparable to Node.js)
- Strong typing support
- Large ecosystem for integrations (payment, messaging)
- Excellent for complex business logic

**Alternatives Considered:**
- Express.js (Node.js): Good option, but Python ecosystem better for business integrations
- Django: Too heavyweight, REST framework is less modern than FastAPI

**Status:** ACCEPTED

---

## ADR-004: Use Next.js for Frontend

**Decision:**
Use Next.js with TypeScript for the frontend.

**Reason:**
- Server-side rendering for public storefront (SEO)
- Static generation for marketing pages
- Client-side SPA for admin dashboards
- Built-in routing
- API routes for BFF pattern if needed
- Strong TypeScript support
- Large ecosystem and community

**Architecture supports multiple portals:**
- Public storefront
- Customer portal
- Salon admin
- Platform super-admin

**Alternatives Considered:**
- React SPA: Lacks SSR for SEO
- Vue/Nuxt: Smaller ecosystem

**Status:** ACCEPTED

---

## ADR-005: Multi-Tenant Architecture from Day One

**Decision:**
Design for multi-tenancy from the beginning. All tenant-specific data must be scoped to salon_id or equivalent.

**Reason:**
- Core product requirement: one platform serves many salons
- Retrofitting multi-tenancy is expensive and risky
- Data isolation is critical for security and compliance
- Enables scalable pricing model (per-tenant billing)

**Implementation:**
- Tenant-aware queries at application level
- Row-level security policies in database
- Separate schemas per tenant (future option)

**Alternatives Considered:**
- Build single-tenant first: Rejected, would require major refactoring

**Status:** ACCEPTED

---

## ADR-006: Use Redis for Caching and Queues

**Decision:**
Use Redis for caching, job queues, and session storage.

**Reason:**
- High-performance in-memory data store
- Supports various data structures
- Pub/sub for real-time notifications
- Job queue capabilities (with libraries)
- Distributed locking
- Session storage

**Use cases:**
- API response caching
- Temporary booking holds
- Background job queues (notifications, reports)
- Rate limiting
- Session management

**Alternatives Considered:**
- Memcached: Lacks data structure support
- RabbitMQ: Overkill for initial needs, Redis sufficient

**Status:** ACCEPTED

---

## ADR-007: Backend as Source of Truth

**Decision:**
Backend is the single source of truth for all business logic, pricing, permissions, and state.

**Reason:**
- Security: Frontend can be manipulated
- Consistency: One place for business rules
- Multi-client support: Mobile, web, integrations all use same API
- Audit trail: Centralized logging

**Frontend responsibilities:**
- UI/UX
- Client-side validation (UX only, not security)
- State management for UI
- Optimistic updates (confirmed by backend)

**Backend responsibilities:**
- Authorization
- Pricing calculation
- Booking availability
- Payment processing
- All business logic

**Status:** ACCEPTED

---

## ADR-008: Migration-Based Database Schema Management

**Decision:**
Use Alembic for database migrations. All schema changes must go through migrations.

**Reason:**
- Version control for database schema
- Repeatable deployments
- Rollback capability
- Team coordination
- Prevents manual schema drift

**Rules:**
- Never edit production database manually
- All changes via migration files
- Migrations tested in development first
- Migrations are code-reviewed

**Status:** ACCEPTED

---

## ADR-009: Environment Isolation

**Decision:**
Maintain strict separation between development, staging, and production environments.

**Rules:**
- Separate databases per environment
- No shared credentials
- Development environment: developid.duckdns.org
- Secrets never committed to repository
- Use environment variables for configuration

**Status:** ACCEPTED

---

## ADR-010: Use Docker for Development Dependencies

**Decision:**
Use Docker containers for PostgreSQL and Redis in development.

**Reason:**
- Consistent development environment
- Easy setup for new developers
- Isolated from host system
- Persistent volumes for data
- Easy to reset/rebuild

**Alternatives Considered:**
- Native installation: Harder to maintain consistency across team
- Manual `docker run` commands: Rejected; Docker Compose plugin is required and installed for reproducible development infrastructure

**Status:** ACCEPTED

---

## ADR-011: Git Branch Strategy

**Decision:**
Use main + develop branches with feature branches.

**Structure:**
- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: Individual features
- `fix/*`: Bug fixes

**Workflow:**
- Develop in feature branches
- Merge to develop for testing
- Merge develop to main for releases

**Status:** ACCEPTED

---

## ADR-012: Use synchronous Psycopg 3 SQLAlchemy foundation

**Decision:**
Use SQLAlchemy synchronous engine with the Psycopg 3 driver (`postgresql+psycopg://`) for Phase 0.

**Reason:**
It gives a small, conventional migration and database foundation while preserving a future path to an async engine if real workload requirements warrant it. Psycopg 3 supports the approved Python 3.14 runtime.

**Alternatives Considered:**
- `psycopg2-binary`: Rejected for this greenfield project.
- Async SQLAlchemy: Deferred; no Phase 0 workload requires it.

**Status:** ACCEPTED

---

## ADR-013: Static tool compatibility target temporarily uses Python 3.13

**Decision:**
Keep project runtime declaration at Python `>=3.14,<3.15`, but configure Ruff and Black with their highest currently accepted static target, `py313`.

**Reason:**
The pinned tooling releases do not yet accept a `py314` target. Runtime dependency installation and tests execute on Python 3.14.7.

**Trade-off:**
Python 3.14-specific syntax is not enabled for static tooling until the tools add a py314 target.

**Status:** ACCEPTED


---

## ADR-014: Modern Compose Specification (compose.yaml)

**Decision:**
Use `compose.yaml` (modern Docker Compose v2 specification) instead of legacy `docker-compose.yml` with top-level `version` attribute.

**Reason:**
- The `version` attribute is deprecated in Compose v2.
- `compose.yaml` is the official preferred filename.
- Pinned image tags (`postgres:16-alpine`, `redis:7-alpine`) ensure reproducible builds.
- Named volumes (`salon_saas_postgres_data`, `salon_saas_redis_data`) provide data persistence.
- Built-in container healthchecks (`pg_isready`, `redis-cli ping`) allow automated readiness detection.

**Status:** ACCEPTED

---

## ADR-015: Server-Side Frontend-to-Backend Connectivity

**Decision:**
Implement Phase 0 frontend-to-API connectivity check server-side in Next.js App Router (Server Component calling FastAPI `/health`).

**Reason:**
- Keeps `API_BASE_URL` server-only — no `NEXT_PUBLIC_*` exposure.
- Avoids browser CORS configuration during Phase 0 foundation.
- Clean architectural boundary: Browser → Next.js (SSR) → FastAPI.
- Server-side error handling degrades gracefully to "API is unavailable" display without browser-side errors.

**Alternatives Considered:**
- Client-side fetch (`NEXT_PUBLIC_API_BASE_URL`): Rejected for Phase 0 to avoid CORS complexity and unnecessary public URL exposure.

**Status:** ACCEPTED

---

## Notes

- ADRs are immutable once accepted
- New decisions append to this log
- Superseded decisions marked as SUPERSEDED with reference to new ADR
