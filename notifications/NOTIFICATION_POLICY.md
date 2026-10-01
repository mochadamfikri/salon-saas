# Notification Policy

## Panel Bell
Store all meaningful lifecycle events.
Do not create noise for individual shell commands or first-attempt transient test failures.

## Telegram Defaults
Send immediately:
- CRITICAL
- OWNER_ACTION_REQUIRED
- worker BLOCKED
- repeated worker crash
- phase activation failure
- security warning

Send optionally:
- SUCCESS checkpoint READY_FOR_AUDIT
- audit PASS
- phase complete

Do not send by default:
- task started
- normal heartbeat
- one failed test attempt that the worker can self-repair

## Deduplication
Repeated identical failures within a short window must collapse into one incident notification with an incrementing count.

## Recovery
When a previously-notified critical incident recovers, emit one recovery notification.
