# Salon SaaS Platform

**Version:** Phase 0 - Foundation  
**Status:** Development

Multi-tenant SaaS platform for beauty salon businesses.

---

## Product Overview

Salon SaaS provides:

**Customer Side:**
- Salon profile and services
- Online booking
- Payment processing
- Booking history

**Salon Operations:**
- Staff management
- Service and product management
- Booking management
- Customer management
- Reports and analytics
- Multi-channel notifications (WhatsApp, Telegram)

---

## Technology Stack

### Frontend
- **Framework:** Next.js 14+ with TypeScript
- **Runtime:** Node.js 24 LTS
- **UI:** TBD (Phase 1+)

### Backend
- **Framework:** FastAPI with Python 3.14
- **ORM:** SQLAlchemy
- **Migrations:** Alembic

### Infrastructure
- **Database:** PostgreSQL 16
- **Cache/Queue:** Redis 7
- **Object Storage:** S3-compatible (future)

### Development
- **Containerization:** Docker & Docker Compose
- **Version Control:** Git (main/develop branches)

---

## Repository Structure

```
salon-saas/
├── apps/
│   ├── web/           # Next.js frontend
│   └── api/           # FastAPI backend
├── packages/
│   ├── ui/            # Shared UI components
│   └── shared/        # Shared utilities and types
├── infra/             # Infrastructure as code
├── docs/              # Project documentation
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── AGENT_RULES.md
│   └── PROGRESS.md
├── scripts/           # Build and deployment scripts
├── docker-compose.yml # Development infrastructure
├── .env.example       # Environment variables template
└── README.md
```

---

## Prerequisites

- **Node.js:** 24 LTS (see `.nvmrc`)
- **Python:** 3.14+ (see `.python-version`)
- **Docker:** 20.10+
- **Docker Compose:** 2.0+ (plugin)
- **Git:** 2.0+

---

## Local Setup

### 1. Clone Repository

```bash
git clone https://github.com/mochadamfikri/salon-saas.git
cd salon-saas
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your local configuration
```

### 3. Start Infrastructure

Start PostgreSQL and Redis:

```bash
docker compose up -d
```

Verify services are running:

```bash
docker compose ps
```

### 4. Backend Setup

```bash
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

### 5. Frontend Setup

```bash
cd apps/web

# Use correct Node version
nvm use  # or: nvm use 24

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at: `http://localhost:3000`

---

## Running Tests

### Backend Tests

```bash
cd apps/api
source .venv/bin/activate
pytest
```

### Frontend Tests

```bash
cd apps/web
npm test
```

---

## Database Migrations

### Create Migration

```bash
cd apps/api
alembic revision --autogenerate -m "description"
```

### Apply Migration

```bash
alembic upgrade head
```

### Rollback Migration

```bash
alembic downgrade -1
```

---

## Environment Variables

See `.env.example` for all required variables.

**Key Variables:**

- `APP_ENV`: Environment (development/staging/production)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `JWT_SECRET`: Secret for JWT token signing
- `API_BASE_URL`: Backend API URL
- `WEB_BASE_URL`: Frontend URL

**Never commit `.env` to repository.**

---

## Development Workflow

### Branch Strategy

- `main`: Production-ready code
- `develop`: Integration branch
- `feature/*`: Feature branches
- `fix/*`: Bug fix branches

### Commit Convention

Follow Conventional Commits:

```
type(scope): description

feat: add user authentication
fix: correct booking availability calculation
docs: update API documentation
test: add booking service tests
```

### Pull Request Process

1. Create feature branch from `develop`
2. Implement changes
3. Write tests
4. Run linting and tests locally
5. Push and create PR to `develop`
6. Wait for CI to pass
7. Request review
8. Merge after approval

---

## Project Commands

### Docker Infrastructure

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f

# Restart service
docker compose restart postgres
```

### Backend

```bash
# Activate virtual environment
source apps/api/.venv/bin/activate

# Run development server
uvicorn app.main:app --reload

# Run tests
pytest

# Run linter
ruff check .

# Format code
black .
```

### Frontend

```bash
# Development server
npm run dev

# Production build
npm run build

# Run tests
npm test

# Lint
npm run lint

# Format
npm run format
```

---

## Architecture

Multi-tenant architecture with tenant isolation:

- Each salon is a tenant with unique `salon_id`
- All tenant data scoped to `salon_id`
- Backend enforces authorization and tenant isolation
- Frontend is presentation layer only

**Key Principles:**
- Backend as source of truth
- No business logic in frontend
- All prices calculated server-side
- Tenant isolation enforced at all layers

See `docs/ARCHITECTURE.md` for detailed architecture documentation.

---

## Phase 0 Status

**Current Phase:** Foundation Engineering

Phase 0 establishes:
- ✅ Repository structure
- ✅ Development environment
- ✅ Backend skeleton
- ✅ Frontend skeleton
- ✅ Database foundation
- ✅ Testing foundation
- ✅ CI pipeline
- ✅ Documentation

**Out of Scope for Phase 0:**
- Authentication system
- Booking logic
- Payment processing
- Notification sending
- Business features

See `docs/PROGRESS.md` for detailed task tracking.

---

## Documentation

- **Architecture:** `docs/ARCHITECTURE.md`
- **Decisions:** `docs/DECISIONS.md`
- **Agent Rules:** `docs/AGENT_RULES.md`
- **Progress:** `docs/PROGRESS.md`

---

## Support

**Project Lead:** Business Owner  
**Engineering:** Hermes Agent  
**Audit:** Product Analyst

---

## License

TBD

---

## Notes

This is a development project in Phase 0 (Foundation).

**Development Environment:** developid.duckdns.org  
**Production Environment:** TBD (separate infrastructure)

Never use production credentials or databases in development.
