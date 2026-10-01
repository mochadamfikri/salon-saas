# Salon Orchestrator Admin Control Panel — Master Spec

## Purpose
Provide the Owner with one mobile-friendly control panel to observe, control, and audit the autonomous engineering system without opening Hermes/Codex terminals for routine operations.

The panel is a **control-plane UI**, not part of the Salon SaaS customer/admin product.
It runs separately from production application services.

## Roles
Initial version has one privileged role:

- `owner_admin`: the project Owner.

Future multi-user ops roles may be added later, but are out of scope for v1.

## Main Navigation
1. Dashboard
2. Workers
3. Queue / Tasks
4. Phases
5. Reports
6. Audits
7. Notifications
8. Business Decisions
9. Logs
10. Settings

---

# 1. Dashboard

The first screen must answer within seconds:
- Is the orchestrator healthy?
- Is Hermes running?
- Is Codex running?
- Is the auditor/notifier running?
- What phase/checkpoint is active?
- Is anything blocked?
- Is anything waiting for Owner input?

## Summary Cards
Show:
- current project phase;
- overall phase status;
- Hermes status;
- Codex status;
- Auditor status;
- Notifier status;
- queued task count;
- tasks ready for audit;
- unread notification count;
- latest backend/frontend SHA.

## Worker Status Values
Canonical values:
- `WAITING`
- `RUNNING`
- `RECOVERING`
- `READY_FOR_AUDIT`
- `BLOCKED`
- `PAUSED`
- `OFFLINE`
- `ERROR`

## Worker Card
Each worker card shows:
- worker name;
- role;
- systemd/service state;
- current task ID;
- phase/checkpoint;
- branch;
- current HEAD SHA;
- working tree clean/dirty;
- last heartbeat;
- uptime for current task;
- retry attempt count;
- last exit code;
- last successful checkpoint;
- context usage when the agent/runtime exposes it;
- last log line summary.

Actions:
- View details
- Pause after current safe point
- Resume
- Retry blocked task
- Refresh status

Dangerous actions are never one-click and never exposed as raw shell.

---

# 2. Workers

Dedicated worker detail pages for:
- Hermes Backend Worker
- Codex Frontend Worker
- Auditor Worker
- Notifier Worker

## Detail Sections
- live state;
- current task;
- task instructions;
- current repository/branch/HEAD;
- heartbeat history;
- retry/recovery history;
- recent reports;
- recent notifications;
- live log tail;
- quality gate snapshot.

## Allowed Control Actions
Panel may request only allowlisted operations:
- pause queue consumption;
- resume queue consumption;
- retry current blocked task;
- mark current queued task cancelled before execution;
- re-run status refresh;
- request clean-session restart after persisted state exists.

Panel MUST NOT provide:
- arbitrary terminal;
- arbitrary shell command input;
- sudo execution;
- production deployment button;
- force-push button;
- direct DB console.

---

# 3. Queue / Tasks

Show separate queues:
- Hermes inbox
- Codex inbox
- Audit queue

## Task List Fields
- task ID;
- target agent;
- phase;
- checkpoint;
- type: implementation / revision / audit / recovery;
- priority;
- state;
- created time;
- started time;
- attempts;
- authoritative SHA/base;
- dependency status.

## Task States
- `DRAFT`
- `QUEUED`
- `RUNNING`
- `WAITING_DEPENDENCY`
- `READY_FOR_AUDIT`
- `REVISE`
- `BLOCKED`
- `FINAL_PASS`
- `CANCELLED`

Owner can open a task and read the exact prompt payload assembled for the agent.

---

# 4. Phases

The Owner can manage project phase packages from the panel.

## Phase Overview
Show:
- Phase number/name;
- status;
- master spec;
- checkpoint graph;
- backend status per checkpoint;
- frontend status per checkpoint;
- unresolved Owner decisions;
- reports/audits linked to the phase.

## Upload Phase
The panel supports upload of:
- a single `PHASE<N>_MASTER_SPEC.md`; or
- a phase package ZIP.

### Recommended ZIP Layout
```
phase-package/
├── PHASE3_MASTER_SPEC.md
├── PHASE3_TASKS.yaml
├── BUSINESS_DECISIONS_APPEND.md   # optional
└── README.md                      # optional
```

## Upload Safety Flow
Upload never activates automatically.

Flow:
1. Upload file/package.
2. Validate filenames, size, MIME/type, and path traversal.
3. Parse manifest if present.
4. Show preview.
5. Show resulting checkpoint/task graph.
6. Show business decisions being appended.
7. Owner presses `Activate Phase`.
8. Control plane writes to orchestration worktree.
9. Commit/push orchestration branch.
10. Dispatcher queues only the first eligible checkpoint(s).

The panel must reject package paths containing `..`, absolute paths, symlinks, or executable binaries.

## Phase Activation Guards
Cannot activate a new phase when:
- current phase has unresolved audit blockers;
- a required Owner decision is missing;
- required baseline report is absent;
- phase package validation fails.

Owner may explicitly override only after a confirmation screen that shows why the guard fired.

---

# 5. Reports

The Owner can retrieve every engineering report without entering the VPS.

## Report Browser
Filter by:
- agent;
- phase;
- checkpoint;
- report type;
- audit status;
- date.

Show:
- report title;
- agent;
- implementation SHA;
- report/docs SHA;
- branch;
- tests summary;
- quality gates;
- audit verdict;
- known warnings;
- creation time.

Actions:
- View Markdown rendered
- View raw Markdown
- Download report
- Copy summary
- Open related GitHub commit
- Download all phase reports as ZIP

## Report Types
- implementation completion report;
- remediation report;
- auditor PASS/REVISE report;
- final phase report;
- incident/recovery report.

---

# 6. Audits

Display audit pipeline separately from engineering reports.

For each audit:
- audited agent;
- checkpoint;
- exact SHA(s);
- source branch;
- verdict;
- findings count;
- revision task generated;
- re-audit count;
- final result.

Verdicts:
- `PASS`
- `REVISE`
- `BLOCKED`

Only the auditor role writes FINAL PASS state.

---

# 7. Notification Bell

Top-right bell with unread badge.

## Levels
- `INFO`
- `SUCCESS`
- `WARNING`
- `CRITICAL`
- `OWNER_ACTION_REQUIRED`

## Events That Create Notifications
Notify on:
- checkpoint READY_FOR_AUDIT;
- audit PASS;
- audit REVISE;
- worker recovery;
- worker BLOCKED;
- repeated worker crash;
- push failure after retry budget;
- Owner business decision required;
- phase ready to activate;
- phase completed;
- security/config anomaly.

Do not notify on every routine command or transient first test failure.

## Bell UX
- unread counter;
- newest first;
- mark read/unread;
- mark all read;
- filter by worker/severity;
- deep-link into task/report/worker.

## Telegram Integration
The same event bus feeds Telegram for WARNING/CRITICAL/OWNER_ACTION_REQUIRED and optionally SUCCESS.
Panel bell remains the complete event history.

---

# 8. Business Decisions

Render `BUSINESS_DECISIONS.md` as structured Owner decisions.

Capabilities:
- browse decisions;
- search;
- filter by phase;
- show which checkpoints depend on each decision;
- add a proposed decision draft;
- Owner approve/reject;
- append approved decision to authoritative knowledge file.

Agents cannot silently approve a business decision.

---

# 9. Logs

Provide safe read-only log viewer.

Sources:
- Hermes worker;
- Codex worker;
- auditor worker;
- notifier;
- orchestrator API.

Features:
- last N lines;
- live stream;
- severity filter;
- search;
- download selected log range.

Secrets/tokens must be redacted before persistence/display.

No arbitrary journalctl arguments from browser.

---

# 10. Settings

Show non-secret operational configuration:
- poll/heartbeat interval;
- retry budget;
- notification preferences;
- worker enable/disable;
- current repository paths;
- current branch assignments;
- Telegram notification enabled/disabled;
- audit cadence;
- retention settings.

Secrets are never displayed after initial configuration.

---

# Real-Time Design

Preferred mechanism:
- worker heartbeat every 5 seconds;
- event bus writes runtime event state;
- admin panel subscribes through Server-Sent Events (SSE);
- REST commands for Owner actions;
- 15-second polling fallback if SSE disconnects.

Worker OFFLINE threshold: 30 seconds without heartbeat, unless deliberately PAUSED.

---

# Mobile UX

The Owner primarily uses Android, so the panel must be mobile-first.

Requirements:
- responsive cards;
- large touch targets;
- no hover-only actions;
- sticky top bar with bell;
- worker state visible without horizontal scrolling;
- reports readable on narrow screens;
- destructive/privileged action confirmations usable on mobile.

---

# Definition of Done for Control Panel v1

- authenticated Owner can open dashboard;
- real-time worker status works;
- bell notifications work;
- task queue can be inspected;
- worker pause/resume/retry works through allowlisted API;
- phase spec/package can be uploaded, validated, previewed, and activated;
- reports can be viewed/downloaded;
- audits are visible and linked to revisions;
- logs are read-only and redacted;
- Telegram critical notification integration works;
- no raw shell/terminal is exposed;
- no production credentials are stored in Git;
- mobile layout is usable on Android.
