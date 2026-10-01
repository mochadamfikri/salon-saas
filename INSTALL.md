# Install Salon SaaS Orchestrator v3

This package contains a runnable initial control-plane runtime, not only specs.

## What the installer does
- creates/uses a dedicated Git branch + worktree named `orchestration` at `/home/ubuntu/salon-orchestrator`;
- leaves `/home/ubuntu/salon-saas` and `/home/ubuntu/salon-saas-frontend` as the engineering worktrees;
- installs a private Python venv;
- starts the admin panel on `127.0.0.1:8787`;
- starts Hermes/Codex queue workers under systemd;
- starts optional Telegram notifier;
- configures Hermes one-shot `single_query_mode: approve` after backing up its config;
- Codex jobs use non-interactive `codex exec`, `workspace-write`, `--ask-for-approval never`;
- does **not** queue Phase 3 automatically.

## Install
Run from the extracted package directory:

```bash
sudo ./salon-orchestrator/bin/install.sh
```

## Mobile access
Create an SSH tunnel from Android/Termux:

```bash
ssh -i ~/storage/downloads/idse.pem -L 8787:127.0.0.1:8787 ubuntu@16.78.106.9
```

Keep that SSH session open and visit `http://127.0.0.1:8787` in the Android browser.
