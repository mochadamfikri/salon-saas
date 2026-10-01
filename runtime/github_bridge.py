from __future__ import annotations

import fcntl
import json
import os
import shutil
import sqlite3
import subprocess
import time
import traceback
from pathlib import Path

from common import ROOT, DB_PATH, emit, now_iso

POLL = int(os.environ.get("GITHUB_BRIDGE_POLL_SECONDS", "30"))
SYNC_REPO = Path(os.environ.get("SALON_SYNC_REPO", "/home/ubuntu/salon-orchestrator-sync"))
LOCK = Path("/tmp/salon-orchestrator-git-sync.lock")


def log(line: str) -> None:
    path = ROOT / "runtime/logs/github-bridge.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {line}\n")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(SYNC_REPO), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def ensure_sync_repo() -> None:
    if not (SYNC_REPO / ".git").exists():
        raise RuntimeError(f"sync repo missing: {SYNC_REPO}")


def copy_selected() -> None:
    for base in (ROOT / "audit", ROOT / "inbox" / "hermes", ROOT / "inbox" / "codex"):
        if not base.exists():
            continue
        for src in base.rglob("*.md"):
            if "/inbox/" in str(src) and not src.name.startswith("REV-"):
                continue
            rel = src.relative_to(ROOT)
            dst = SYNC_REPO / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def build_state() -> None:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    audits = [
        dict(r)
        for r in con.execute(
            "SELECT id,target_agent,phase,checkpoint,state,created_at,started_at,finished_at,"
            "attempts,authoritative_sha,last_error,result_path "
            "FROM tasks WHERE target_agent='auditor' ORDER BY created_at"
        ).fetchall()
    ]
    workers = [
        dict(r)
        for r in con.execute(
            "SELECT id,role,status,current_task_id,phase,checkpoint,branch,head_sha,last_heartbeat,"
            "current_stage,current_activity,progress_pct,last_successful_checkpoint "
            "FROM workers ORDER BY id"
        ).fetchall()
    ]
    con.close()

    state = SYNC_REPO / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "audit-index.json").write_text(
        json.dumps(
            {"schema_version": 1, "generated_at": now_iso(), "audits": audits},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (state / "runtime-snapshot.json").write_text(
        json.dumps(
            {"schema_version": 1, "generated_at": now_iso(), "workers": workers},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def sync_once() -> None:
    ensure_sync_repo()
    LOCK.touch(exist_ok=True)
    with LOCK.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        git("fetch", "origin", "orchestration")
        git("checkout", "-B", "orchestration", "origin/orchestration")
        git("clean", "-fd", check=False)

        copy_selected()
        build_state()

        git("add", "audit", "state/audit-index.json", "state/runtime-snapshot.json", check=False)
        git("add", "inbox/hermes", "inbox/codex", check=False)

        if git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return

        git("config", "user.name", "IDSE Orchestrator")
        git("config", "user.email", "orchestrator@idse.local")
        git("commit", "-m", "chore(orchestrator): sync audit evidence and runtime state")

        pushed = git("push", "origin", "HEAD:orchestration", check=False)
        if pushed.returncode != 0:
            git("fetch", "origin", "orchestration")
            rebased = git("rebase", "origin/orchestration", check=False)
            if rebased.returncode != 0:
                git("rebase", "--abort", check=False)
                raise RuntimeError("git bridge rebase failed: " + rebased.stdout[-1200:])
            pushed = git("push", "origin", "HEAD:orchestration", check=False)
            if pushed.returncode != 0:
                raise RuntimeError("git bridge push failed: " + pushed.stdout[-1200:])

        log("Synced audit evidence/state to orchestration")


def main() -> None:
    emit(
        "orchestrator",
        "github_bridge.online",
        "INFO",
        "GitHub Audit Bridge online",
        "Audit/state synchronization started",
    )
    while True:
        try:
            sync_once()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            log("ERROR " + repr(exc) + " | " + traceback.format_exc()[-2000:])
            emit(
                "orchestrator",
                "github_bridge.error",
                "CRITICAL",
                "GitHub Audit Bridge error",
                str(exc),
            )
        time.sleep(POLL)


if __name__ == "__main__":
    main()
