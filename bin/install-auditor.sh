#!/usr/bin/env bash
set -euo pipefail

OWNER_USER="${SUDO_USER:-ubuntu}"
OWNER_HOME="$(getent passwd "$OWNER_USER" | cut -d: -f6)"
ORCH="${SALON_ORCHESTRATOR:-$OWNER_HOME/salon-orchestrator}"
VENV="$OWNER_HOME/.venvs/salon-orchestrator"
ENV_FILE=/etc/salon-orchestrator/worker.env

[[ -e "$ORCH/.git" ]] || { echo "ERROR: orchestration worktree not found at $ORCH"; exit 1; }
[[ -x "$VENV/bin/python" ]] || { echo "ERROR: orchestrator venv missing at $VENV"; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "ERROR: $ENV_FILE missing"; exit 1; }

AUDITOR_BIN="$(sudo -u "$OWNER_USER" -H bash -lc 'command -v codex' || true)"
[[ -n "$AUDITOR_BIN" ]] || { echo "ERROR: codex CLI not found for $OWNER_USER"; exit 1; }

append_if_missing() {
  local key="$1" value="$2"
  if ! sudo grep -q "^${key}=" "$ENV_FILE"; then
    printf '%s=%s\n' "$key" "$value" | sudo tee -a "$ENV_FILE" >/dev/null
  fi
}
append_if_missing AUDITOR_BIN "$AUDITOR_BIN"
append_if_missing AUDITOR_CODEX_HOME "$OWNER_HOME/.codex-muse"
append_if_missing AUDITOR_POLL_SECONDS "30"

sudo chmod 600 "$ENV_FILE"
sudo tee /etc/systemd/system/salon-auditor-worker.service >/dev/null <<EOF2
[Unit]
Description=Salon SaaS Independent Auditor Worker
After=network-online.target salon-orchestrator-panel.service
Wants=network-online.target

[Service]
Type=simple
User=$OWNER_USER
WorkingDirectory=$ORCH/runtime
Environment=HOME=$OWNER_HOME
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/python $ORCH/runtime/auditor.py
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF2

sudo systemctl daemon-reload
sudo systemctl enable --now salon-auditor-worker
sleep 3

echo "=== AUDITOR STATUS ==="
systemctl is-active salon-auditor-worker || true
systemctl status salon-auditor-worker --no-pager -l | sed -n '1,18p' || true

echo
echo "The seeded P2-D audit will start first. P2-E waits for P2-D FINAL_PASS."
