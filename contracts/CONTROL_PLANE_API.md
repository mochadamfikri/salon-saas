# Control Plane API Contract — v1

This is the UI/backend contract for the standalone orchestrator admin panel.

## Read APIs
- `GET /api/health`
- `GET /api/project`
- `GET /api/workers`
- `GET /api/workers/{worker_id}`
- `GET /api/workers/{worker_id}/logs?limit=N`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/phases`
- `GET /api/phases/{phase_id}`
- `GET /api/reports`
- `GET /api/reports/{report_id}`
- `GET /api/audits`
- `GET /api/notifications`
- `GET /api/business-decisions`
- `GET /api/events/stream` (SSE)

## Worker Actions
- `POST /api/workers/{worker_id}/pause`
- `POST /api/workers/{worker_id}/resume`
- `POST /api/workers/{worker_id}/retry`
- `POST /api/workers/{worker_id}/refresh`

No generic command endpoint exists.

## Task Actions
- `POST /api/tasks` (create Owner-authored task draft/queue item)
- `POST /api/tasks/{task_id}/cancel` (queued only)
- `POST /api/tasks/{task_id}/retry` (blocked/retriable only)

## Phase Actions
- `POST /api/phases/upload`
- `POST /api/phases/{phase_id}/validate`
- `GET /api/phases/{phase_id}/preview`
- `POST /api/phases/{phase_id}/activate`

Activation is a distinct Owner action; upload alone never activates.

## Report Actions
- `GET /api/reports/{report_id}/download`
- `GET /api/phases/{phase_id}/reports.zip`

## Notification Actions
- `POST /api/notifications/{notification_id}/read`
- `POST /api/notifications/{notification_id}/unread`
- `POST /api/notifications/read-all`

## Business Decision Actions
- `POST /api/business-decisions/drafts`
- `POST /api/business-decisions/{decision_id}/approve`
- `POST /api/business-decisions/{decision_id}/reject`

## Authentication
Every endpoint except health/login requires Owner session.
Every state-changing endpoint requires CSRF protection.
