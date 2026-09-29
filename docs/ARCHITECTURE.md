# Salon SaaS Platform Architecture

**Version:** Phase 0  
**Status:** Foundation  
**Last Updated:** 2026-09-29

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Technology Stack](#technology-stack)
4. [System Components](#system-components)
5. [Multi-Tenant Architecture](#multi-tenant-architecture)
6. [Data Architecture](#data-architecture)
7. [API Architecture](#api-architecture)
8. [Frontend Architecture](#frontend-architecture)
9. [Security Architecture](#security-architecture)
10. [Deployment Architecture](#deployment-architecture)
11. [Future Considerations](#future-considerations)

---

## System Overview

Salon SaaS is a multi-tenant platform designed to serve beauty salon businesses. The platform provides two primary user-facing applications:

1. **Public/Customer Side:** Booking, services, products, payments
2. **Salon Operational Side:** Management dashboard, staff, inventory, reporting

### Key Characteristics

- **Multi-tenant:** One deployment serves multiple salon businesses
- **SaaS Model:** Cloud-hosted, subscription-based
- **Real-time:** Booking availability, notifications, updates
- **Integrated:** Payment gateways, messaging (WhatsApp, Telegram)
- **Scalable:** Designed to grow from 1 to 1000+ salons

---

## Architecture Principles

### 1. Multi-Tenant from Day One

The platform is designed as a true multi-tenant system where:
- One codebase serves all tenants
- Data is logically isolated per tenant
- Resources are shared efficiently
- Tenant-specific customization is supported

### 2. Backend as Source of Truth

All business logic, authorization, pricing, and critical operations happen server-side:
- Frontend is presentation layer only
- Backend validates all operations
- No critical logic in client code
- Single source of truth for state

### 3. Domain-Driven Design

Architecture follows business domains:
- Clear bounded contexts
- Domain models reflect business reality
- Ubiquitous language used throughout
- Clean separation of concerns

### 4. Security First

Security is not an afterthought:
- Authentication and authorization built-in
- Tenant isolation enforced
- Input validation at all layers
- Secrets management
- Audit logging

### 5. API-First

The API is the product:
- Well-documented OpenAPI/Swagger
- Versioned endpoints
- Consistent error handling
- Multiple client support (web, mobile, integrations)

---

## Technology Stack

### Frontend

**Framework:** Next.js 16.x Active LTS with TypeScript

**Key Features:**
- Server-side rendering for SEO (public pages)
- Static generation for marketing content
- Client-side rendering for dashboards
- Built-in routing and API routes
- Image optimization

**UI Library:**
- Component library: TBD (Phase 1)
- Styling: TBD (Tailwind CSS likely)
- State management: React Context / Zustand / TBD

### Backend

**Framework:** FastAPI with Python 3.14

**Key Features:**
- Async/await for high performance
- Automatic OpenAPI documentation
- Pydantic for data validation
- Type hints throughout
- Dependency injection

**Key Libraries:**
- SQLAlchemy 2.0: ORM
- Alembic 1.20: Database migrations
- Pydantic 2.13: Data validation
- Psycopg 3: PostgreSQL driver (`postgresql+psycopg://`)
- python-jose: JWT handling (Phase 1+)
- passlib: Password hashing (Phase 1+)

### Database

**Primary Database:** PostgreSQL 16

**Reasons:**
- Strong ACID compliance
- Advanced relational features
- JSON support for flexibility
- Row-level security
- Proven scalability

**Schema Design:**
- Normalized for data integrity
- Tenant-scoped tables
- Migration-based schema evolution
- Indexes for performance

### Cache & Queue

**Redis 7+**

**Use Cases:**
- API response caching
- Session storage
- Job queues (background tasks)
- Rate limiting
- Temporary booking holds
- Pub/sub for real-time updates

### Object Storage

**S3-Compatible Storage**

**Stored Assets:**
- Salon logos and banners
- Service and product images
- Staff photos
- Invoice attachments
- Ticket attachments

**Note:** Local filesystem not used for permanent storage.

---

## System Components

### Monorepo Structure

```
salon-saas/
├── apps/
│   ├── web/           # Next.js frontend application
│   └── api/           # FastAPI backend application
├── packages/
│   ├── ui/            # Shared React components
│   └── shared/        # Shared utilities, types, constants
├── infra/             # Infrastructure as code (future)
├── docs/              # Project documentation
├── scripts/           # Build and deployment scripts
└── compose.yaml       # Local development environment
```

### Application Boundaries

**apps/web:**
- Public storefront
- Customer portal
- Salon admin dashboard
- Platform super-admin (future)
- Shared UI components in packages/ui

**apps/api:**
- RESTful API endpoints
- Business logic
- Database access
- External integrations
- Background jobs

**packages/shared:**
- TypeScript type definitions
- Shared constants
- Utility functions
- Validation schemas

---

## Multi-Tenant Architecture

### Tenant Identification

Each salon is a tenant with unique `salon_id`.

**Tenant Context:**
- Resolved from authenticated user session
- Attached to request context
- Used to scope all queries
- Enforced at application and database level

### Data Isolation

**Application-Level:**
```python
# All queries must include tenant scope
bookings = db.query(Booking).filter(
    Booking.salon_id == current_tenant.salon_id
).all()
```

**Database-Level (Future):**
- Row-level security policies
- Separate schemas per tenant (optional)
- Audit logging per tenant

### Tenant-Aware Resources

**Tenant-Specific:**
- Salons (obviously)
- Branches
- Staff
- Services
- Products
- Bookings
- Customers
- Invoices
- Settings

**Shared/Platform:**
- User authentication records
- System configuration
- Audit logs
- Analytics aggregations

### Onboarding Flow (Future Phases)

1. Salon registration
2. Create salon record (tenant)
3. Initialize default settings
4. Create admin user
5. Set up branches
6. Configure services
7. Go live

---

## Data Architecture

### Core Entities (High-Level)

**Phase 0 Note:** Full schema design happens in Phase 1+. This is directional only.

**Salon Management:**
- Salon (tenant)
- Branch (location)
- Staff
- OperatingHours

**Service Management:**
- Service
- ServiceCategory
- Product
- Pricing

**Booking System:**
- Booking
- BookingItem
- Schedule
- Availability

**Customer Management:**
- Customer
- CustomerProfile
- CustomerHistory

**Financial:**
- Invoice
- Payment
- Transaction
- Commission

**Notification:**
- NotificationConfig
- NotificationLog

### Relationships

- One Salon → Many Branches
- One Salon → Many Staff
- One Salon → Many Services
- One Salon → Many Customers
- One Customer → Many Bookings
- One Booking → Many BookingItems
- One Booking → One Invoice

### Migration Strategy

- Alembic for all schema changes
- Version-controlled migrations
- Forward migrations required
- Rollback migrations recommended
- Tested in development before staging/production

---

## API Architecture

### REST API Design

**Base URL:** `/api/v1`

**Versioning:**
- URL-based versioning (/v1, /v2)
- Breaking changes require new version
- Old versions supported for transition period

**Endpoints Pattern:**
```
GET    /api/v1/salons/{salon_id}/services
POST   /api/v1/salons/{salon_id}/services
GET    /api/v1/salons/{salon_id}/services/{service_id}
PUT    /api/v1/salons/{salon_id}/services/{service_id}
DELETE /api/v1/salons/{salon_id}/services/{service_id}
```

**Response Format:**
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful",
  "meta": {
    "timestamp": "2026-09-29T10:00:00Z",
    "request_id": "uuid"
  }
}
```

**Error Format:**
```json
{
  "success": false,
  "error": {
    "code": "BOOKING_NOT_AVAILABLE",
    "message": "The selected time slot is no longer available",
    "details": { ... }
  },
  "meta": {
    "timestamp": "2026-09-29T10:00:00Z",
    "request_id": "uuid"
  }
}
```

### Authentication & Authorization

**Authentication:** JWT-based (Phase 1+)
- Access token (short-lived)
- Refresh token (long-lived)
- Token stored in HTTP-only cookie or Authorization header

**Authorization:**
- Role-based access control (RBAC)
- Tenant-scoped permissions
- Resource-level permissions

**User Roles:**
- Platform Admin (super user)
- Salon Owner
- Salon Manager
- Staff Member
- Customer

### Rate Limiting

- Redis-backed rate limiting
- Per-user and per-IP limits
- Configurable per endpoint
- 429 Too Many Requests response

---

## Frontend Architecture

### Application Structure

```
apps/web/
├── app/                  # Next.js App Router
│   ├── (public)/        # Public pages (storefront)
│   ├── (customer)/      # Customer portal
│   ├── (salon)/         # Salon dashboard
│   └── api/             # API routes (BFF if needed)
├── components/
│   ├── ui/              # UI primitives
│   ├── features/        # Feature-specific components
│   └── layouts/         # Layout components
├── lib/
│   ├── api/             # API client
│   ├── auth/            # Authentication helpers
│   └── utils/           # Utilities
└── styles/              # Global styles
```

### Routing Strategy

**Public Routes:**
- `/` - Homepage
- `/salon/{slug}` - Salon profile
- `/salon/{slug}/services` - Services listing
- `/salon/{slug}/booking` - Booking flow

**Customer Routes:**
- `/customer/dashboard`
- `/customer/bookings`
- `/customer/profile`

**Salon Routes:**
- `/salon/dashboard`
- `/salon/bookings`
- `/salon/services`
- `/salon/staff`
- `/salon/customers`
- `/salon/reports`
- `/salon/settings`

### State Management

- Server state: React Query / SWR
- UI state: React Context / Zustand
- Form state: React Hook Form
- Optimistic updates where appropriate

### Data Fetching

- Server Components for initial data (SSR)
- Client Components for interactive data
- SWR/React Query for caching and revalidation
- Prefetching for navigation

---

## Security Architecture

### Defense in Depth

Multiple layers of security:

1. **Network Layer:**
   - HTTPS only
   - CORS configuration
   - Rate limiting
   - DDoS protection (future)

2. **Application Layer:**
   - Input validation
   - Output encoding
   - CSRF protection
   - SQL injection prevention (parameterized queries)

3. **Data Layer:**
   - Encrypted at rest (database)
   - Encrypted in transit (TLS)
   - Tenant isolation
   - Audit logging

4. **Access Control:**
   - Authentication required
   - Role-based authorization
   - Resource-level permissions
   - Tenant verification

### Secrets Management

**Development:**
- `.env` files (gitignored)
- `.env.example` template

**Production:**
- Environment variables
- Secrets manager (AWS Secrets Manager / similar)
- Never in code or logs

### Security Headers

- Content-Security-Policy
- X-Frame-Options
- X-Content-Type-Options
- Strict-Transport-Security
- X-XSS-Protection

---

## Deployment Architecture

### Environments

**Development:**
- Local Docker containers
- PostgreSQL + Redis local
- Hot reload enabled
- Debug logging
- Host: developid.duckdns.org

**Staging:**
- Production-like environment
- Separate database
- Integration testing
- Performance testing

**Production:**
- High availability
- Load balanced
- Database backups
- Monitoring and alerting

### Environment Variables

**Required for all environments:**
```bash
APP_ENV=development|staging|production
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
JWT_SECRET=...
API_BASE_URL=...
WEB_BASE_URL=...
```

**Optional:**
```bash
OBJECT_STORAGE_ENDPOINT=...
WHATSAPP_API_KEY=...
TELEGRAM_BOT_TOKEN=...
PAYMENT_GATEWAY_KEY=...
```

### CI/CD Pipeline (Phase 0+)

**On Pull Request:**
1. Run linters
2. Run tests
3. Build verification

**On Merge to develop:**
1. Run full test suite
2. Build artifacts
3. Deploy to staging (future)

**On Merge to main:**
1. Tag release
2. Build production artifacts
3. Deploy to production (manual approval)

---

## Future Considerations

### Scalability

**Database:**
- Read replicas for reporting
- Connection pooling
- Query optimization
- Partitioning by tenant (large scale)

**Application:**
- Horizontal scaling
- Stateless API servers
- Load balancing
- CDN for static assets

**Caching:**
- Redis cluster
- Application-level caching
- CDN caching

### Observability

**Logging:**
- Structured logging
- Centralized log aggregation
- Tenant-specific logs

**Monitoring:**
- Application metrics
- Database metrics
- Business metrics
- Uptime monitoring

**Tracing:**
- Distributed tracing
- Performance profiling
- Error tracking (Sentry)

### Additional Integrations

- Payment gateways (Stripe, Xendit)
- WhatsApp Business API
- Telegram Bot API
- SMS providers
- Email service (SendGrid, AWS SES)
- Calendar integrations (Google Calendar)
- Accounting software integrations

### Mobile Applications

- React Native or Flutter
- Shared API with web
- Push notifications
- Offline support

---

## Conclusion

This architecture is designed for:
- **Maintainability:** Clean separation of concerns
- **Scalability:** Horizontal scaling capability
- **Security:** Defense in depth
- **Developer Experience:** Clear conventions and tooling
- **Business Growth:** Multi-tenant, feature-rich platform

The architecture will evolve as the platform grows, but these foundational decisions provide a solid base for future development.

---

**Document Status:** Living document, updated per phase  
**Next Review:** After Phase 1 completion
