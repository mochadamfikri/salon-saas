#!/usr/bin/env bash
set -euo pipefail

OWNER_USER="${SUDO_USER:-ubuntu}"
OWNER_HOME="$(getent passwd "$OWNER_USER" | cut -d: -f6)"
REPO="${SALON_REPO:-$OWNER_HOME/salon-saas}"
FRONT="${SALON_FRONTEND:-$OWNER_HOME/salon-saas-frontend}"
ORCH="${SALON_ORCHESTRATOR:-$OWNER_HOME/salon-orchestrator}"
PKG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$OWNER_HOME/.venvs/salon-orchestrator"

echo "== Salon SaaS Orchestrator v3 installer =="
echo "Owner user : $OWNER_USER"
echo "Backend    : $REPO"
echo "Frontend   : $FRONT"
echo "Orchestrator: $ORCH"

[[ -e "$REPO/.git" ]] || { echo "ERROR: backend git repo not found at $REPO"; exit 1; }
[[ -e "$FRONT/.git" ]] || { echo "ERROR: frontend git worktree not found at $FRONT"; exit 1; }

HERMES_BIN="$(sudo -u "$OWNER_USER" -H bash -lc 'command -v hermes' || true)"
CODEX_BIN="$(sudo -u "$OWNER_USER" -H bash -lc 'command -v codex' || true)"
[[ -n "$HERMES_BIN" ]] || { echo "ERROR: hermes CLI not found for $OWNER_USER"; exit 1; }
[[ -n "$CODEX_BIN" ]] || { echo "ERROR: codex CLI not found for $OWNER_USER"; exit 1; }
echo "Hermes CLI : $HERMES_BIN"
echo "Codex CLI  : $CODEX_BIN"

sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip sqlite3 git rsync

# 1) Create a dedicated orchestration branch/worktree. This does not edit
#    Hermes or Codex worktrees.
sudo -u "$OWNER_USER" git -C "$REPO" fetch origin
if [[ ! -e "$ORCH/.git" ]]; then
  if [[ -e "$ORCH" ]] && [[ -n "$(ls -A "$ORCH" 2>/dev/null || true)" ]]; then
    echo "ERROR: $ORCH already exists and is not an orchestration git worktree."
    echo "Move/remove it first, then rerun installer."
    exit 1
  fi
  rm -rf "$ORCH"

  if sudo -u "$OWNER_USER" git -C "$REPO" show-ref --verify --quiet refs/heads/orchestration; then
    sudo -u "$OWNER_USER" git -C "$REPO" worktree add "$ORCH" orchestration
  elif sudo -u "$OWNER_USER" git -C "$REPO" ls-remote --exit-code --heads origin orchestration >/dev/null 2>&1; then
    sudo -u "$OWNER_USER" git -C "$REPO" branch --track orchestration origin/orchestration
    sudo -u "$OWNER_USER" git -C "$REPO" worktree add "$ORCH" orchestration
  else
    sudo -u "$OWNER_USER" git -C "$REPO" worktree add -b orchestration "$ORCH" origin/develop
    sudo -u "$OWNER_USER" git -C "$ORCH" push -u origin orchestration
  fi
fi

# 2) Copy the runtime/scaffold into the dedicated worktree.
sudo -u "$OWNER_USER" rsync -a --exclude='.git' "$PKG_DIR/" "$ORCH/"
sudo -u "$OWNER_USER" mkdir -p \
  "$ORCH/runtime/logs" \
  "$ORCH/runtime/prompts" \
  "$ORCH/runtime/results" \
  "$ORCH/runtime/uploads"

# 3) Python runtime.
sudo -u "$OWNER_USER" mkdir -p "$OWNER_HOME/.venvs"
sudo -u "$OWNER_USER" python3 -m venv "$VENV"
sudo -u "$OWNER_USER" "$VENV/bin/pip" install --upgrade pip
sudo -u "$OWNER_USER" "$VENV/bin/pip" install -r "$ORCH/requirements.txt"

# 4) Hermes unattended mode. Backup first. We only change the one-shot
#    approval policy; interactive approvals stay under the existing mode.
HCFG="$OWNER_HOME/.hermes/config.yaml"
if [[ -f "$HCFG" ]]; then
  BACKUP="$HCFG.before-salon-orchestrator-$(date +%Y%m%d-%H%M%S).bak"
  sudo -u "$OWNER_USER" cp -a "$HCFG" "$BACKUP"
  sudo -u "$OWNER_USER" "$VENV/bin/python" - "$HCFG" <<'PY'
import sys, yaml
path=sys.argv[1]
with open(path, encoding='utf-8') as f:
    data=yaml.safe_load(f) or {}
approvals=data.setdefault('approvals', {})
approvals['single_query_mode']='approve'
with open(path, 'w', encoding='utf-8') as f:
    yaml.safe_dump(data, f, sort_keys=False)
PY
  echo "Hermes config backup: $BACKUP"
else
  echo "WARNING: $HCFG not found. Hermes one-shot may block dangerous commands until configured."
fi

# 5) Secret/config files live outside Git.
sudo mkdir -p /etc/salon-orchestrator
if [[ ! -f /etc/salon-orchestrator/panel.env ]]; then
  PASS="$(python3 - <<'PY'
import secrets, string
chars=string.ascii_letters+string.digits+'-_'
print(''.join(secrets.choice(chars) for _ in range(24)))
PY
)"
  SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(48))
PY
)"
  sudo tee /etc/salon-orchestrator/panel.env >/dev/null <<EOF
SALON_ORCHESTRATOR_ROOT=$ORCH
SALON_ADMIN_USER=owner
SALON_ADMIN_PASSWORD=$PASS
SALON_ADMIN_SESSION_SECRET=$SECRET
SALON_COOKIE_SECURE=false
EOF
  sudo chmod 600 /etc/salon-orchestrator/panel.env
  printf '%s\n' "$PASS" | sudo -u "$OWNER_USER" tee "$OWNER_HOME/.salon-orchestrator-first-password" >/dev/null
  sudo -u "$OWNER_USER" chmod 600 "$OWNER_HOME/.salon-orchestrator-first-password"
fi

if [[ ! -f /etc/salon-orchestrator/worker.env ]]; then
  sudo tee /etc/salon-orchestrator/worker.env >/dev/null <<EOF
SALON_ORCHESTRATOR_ROOT=$ORCH
HERMES_WORKSPACE=$REPO
CODEX_WORKSPACE=$FRONT
HERMES_BIN=$HERMES_BIN
CODEX_BIN=$CODEX_BIN
CODEX_HOME=$OWNER_HOME/.codex-muse
WORKER_POLL_SECONDS=30
WORKER_MAX_ATTEMPTS=3
NOTIFIER_POLL_SECONDS=15
TELEGRAM_LEVELS=SUCCESS,WARNING,CRITICAL,OWNER_ACTION_REQUIRED
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=
EOF
  sudo chmod 600 /etc/salon-orchestrator/worker.env
fi

# 6) systemd services. They run as the normal ubuntu owner, never root.
sudo tee /etc/systemd/system/salon-orchestrator-panel.service >/dev/null <<EOF
[Unit]
Description=Salon SaaS Orchestrator Admin Panel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$OWNER_USER
WorkingDirectory=$ORCH/runtime
Environment=HOME=$OWNER_HOME
EnvironmentFile=/etc/salon-orchestrator/panel.env
EnvironmentFile=/etc/salon-orchestrator/worker.env
ExecStart=$VENV/bin/uvicorn app:app --host 127.0.0.1 --port 8787
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

for AGENT in hermes codex; do
  TITLE="Hermes"
  [[ "$AGENT" == "codex" ]] && TITLE="Codex"
  sudo tee "/etc/systemd/system/salon-${AGENT}-worker.service" >/dev/null <<EOF
[Unit]
Description=Salon SaaS $TITLE Worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$OWNER_USER
WorkingDirectory=$ORCH/runtime
Environment=HOME=$OWNER_HOME
EnvironmentFile=/etc/salon-orchestrator/worker.env
ExecStart=$VENV/bin/python $ORCH/runtime/worker.py $AGENT
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
done

sudo tee /etc/systemd/system/salon-notifier.service >/dev/null <<EOF
[Unit]
Description=Salon SaaS Orchestrator Notifier
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$OWNER_USER
WorkingDirectory=$ORCH/runtime
Environment=HOME=$OWNER_HOME
EnvironmentFile=/etc/salon-orchestrator/worker.env
ExecStart=$VENV/bin/python $ORCH/runtime/notifier.py
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# 7) Commit the control-plane runtime on orchestration branch only.
sudo -u "$OWNER_USER" git -C "$ORCH" add .
if ! sudo -u "$OWNER_USER" git -C "$ORCH" diff --cached --quiet; then
  sudo -u "$OWNER_USER" git -C "$ORCH" commit -m "chore(orchestrator): install control plane runtime v3"
  sudo -u "$OWNER_USER" git -C "$ORCH" push origin orchestration
fi

# 8) Start services. Inboxes are empty, so Hermes/Codex start WAITING and
#    do not modify the engineering repos until an explicit task is queued.
sudo systemctl daemon-reload
sudo systemctl enable --now \
  salon-orchestrator-panel \
  salon-hermes-worker \
  salon-codex-worker \
  salon-notifier
sleep 3

echo
echo "=== SERVICE STATUS ==="
for S in salon-orchestrator-panel salon-hermes-worker salon-codex-worker salon-notifier; do
  systemctl is-active "$S" | sed "s/^/$S: /" || true
done

echo
echo "=== ADMIN PANEL ==="
echo "Panel is bound safely to VPS localhost:8787"
echo "Username: owner"
echo -n "Password: "
cat "$OWNER_HOME/.salon-orchestrator-first-password"
echo
echo "Android tunnel command:"
echo "ssh -i ~/storage/downloads/idse.pem -L 8787:127.0.0.1:8787 ubuntu@16.78.106.9"
echo "Then open: http://127.0.0.1:8787"
echo
echo "Telegram is optional. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to:"
echo "/etc/salon-orchestrator/worker.env"
echo "then: sudo systemctl restart salon-notifier"
echo
echo "IMPORTANT: No Phase 3 task is queued by this installer. Both engineering workers remain WAITING."
