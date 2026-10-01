# Salon Orchestrator Admin Panel

Standalone Owner-facing control panel for the engineering orchestrator.

## Recommended Implementation
- API/control backend: FastAPI (Python)
- runtime state: SQLite
- realtime: Server-Sent Events (SSE)
- UI: responsive web frontend, mobile-first
- reverse proxy: Nginx or equivalent
- service supervision: systemd

This panel is deliberately separate from the Salon SaaS product UI.

## Required Pages
- `/` Dashboard
- `/workers`
- `/workers/{id}`
- `/tasks`
- `/phases`
- `/phases/{id}`
- `/reports`
- `/audits`
- `/notifications`
- `/business-decisions`
- `/logs`
- `/settings`

## v1 Non-Goals
- production deployment orchestration
- generic SSH/terminal
- database console
- force-push/merge buttons
- customer/salon SaaS administration
