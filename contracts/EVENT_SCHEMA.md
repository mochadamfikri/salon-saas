# Orchestrator Event Schema

Every runtime event uses a normalized envelope.

```json
{
  "id": "evt_...",
  "timestamp": "ISO-8601",
  "source": "hermes|codex|auditor|notifier|orchestrator",
  "type": "worker.blocked",
  "severity": "INFO|SUCCESS|WARNING|CRITICAL|OWNER_ACTION_REQUIRED",
  "phase": 2,
  "checkpoint": "P2-E",
  "task_id": "...",
  "title": "Hermes blocked",
  "message": "Short human-readable summary",
  "links": {
    "worker": "hermes",
    "report_id": null,
    "audit_id": null
  },
  "metadata": {}
}
```

## Minimum Event Types
- `worker.online`
- `worker.offline`
- `worker.running`
- `worker.waiting`
- `worker.recovering`
- `worker.blocked`
- `worker.error`
- `task.queued`
- `task.started`
- `task.ready_for_audit`
- `task.completed`
- `task.cancelled`
- `audit.pass`
- `audit.revise`
- `audit.blocked`
- `phase.uploaded`
- `phase.validation_failed`
- `phase.ready_to_activate`
- `phase.activated`
- `phase.completed`
- `owner.decision_required`
- `git.push_failed`
- `security.warning`

The panel notification bell is driven from this event stream.
Telegram consumes selected severities from the same source.
