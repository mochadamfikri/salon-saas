# Runtime State Model

Git remains source of truth for code/spec/report artifacts.
Runtime UI state should use a small local state store (SQLite recommended) for heartbeats, notification read/unread state, task attempts, and transient worker state.

## Worker
Fields:
- id
- role
- status
- service_state
- pid
- last_heartbeat_at
- current_task_id
- phase
- checkpoint
- branch
- head_sha
- worktree_clean
- task_started_at
- attempt
- retry_budget
- last_exit_code
- last_error_summary
- context_usage_percent nullable

## Task
Fields:
- id
- target_agent
- phase
- checkpoint
- type
- state
- priority
- authoritative_base_sha
- task_file_path
- created_at
- started_at
- finished_at
- attempts
- result_sha nullable
- report_path nullable

## Notification
Fields:
- id
- event_id
- severity
- title
- message
- is_read
- created_at
- deep_link

## Phase Upload
Fields:
- id
- phase_number
- source_filename
- staging_path
- validation_state
- preview_manifest
- activated_at nullable
- orchestration_commit_sha nullable

SQLite is runtime state only; authoritative specs/reports remain versioned files/Git.
