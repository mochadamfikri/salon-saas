#!/usr/bin/env bash
set -euo pipefail
for S in salon-orchestrator-panel salon-hermes-worker salon-codex-worker salon-notifier; do
  printf '%-32s %s\n' "$S" "$(systemctl is-active "$S" 2>/dev/null || true)"
done
echo
sqlite3 /home/ubuntu/salon-orchestrator/runtime/orchestrator.db \
  "select id,status,coalesce(current_task_id,'-'),coalesce(checkpoint,'-'),last_heartbeat from workers order by id;" \
  2>/dev/null || true
