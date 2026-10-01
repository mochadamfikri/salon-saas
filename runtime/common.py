from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("SALON_ORCHESTRATOR_ROOT", "/home/ubuntu/salon-orchestrator"))
RUNTIME = ROOT / "runtime"
DB_PATH = Path(os.environ.get("SALON_ORCHESTRATOR_DB", str(RUNTIME / "orchestrator.db")))
BACKEND_WORKSPACE = Path(os.environ.get("HERMES_WORKSPACE", "/home/ubuntu/salon-saas"))
FRONTEND_WORKSPACE = Path(os.environ.get("CODEX_WORKSPACE", "/home/ubuntu/salon-saas-frontend"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    return con


def init_db() -> None:
    con = db()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS workers (
          id TEXT PRIMARY KEY,
          role TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'WAITING',
          current_task_id TEXT,
          phase INTEGER,
          checkpoint TEXT,
          branch TEXT,
          head_sha TEXT,
          working_tree_clean INTEGER,
          last_heartbeat TEXT,
          task_started_at TEXT,
          retry_attempt INTEGER NOT NULL DEFAULT 0,
          last_exit_code INTEGER,
          last_successful_checkpoint TEXT,
          last_log TEXT,
          paused INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          target_agent TEXT NOT NULL,
          phase INTEGER,
          checkpoint TEXT,
          type TEXT NOT NULL DEFAULT 'implementation',
          priority INTEGER NOT NULL DEFAULT 100,
          state TEXT NOT NULL DEFAULT 'QUEUED',
          task_path TEXT NOT NULL,
          created_at TEXT NOT NULL,
          started_at TEXT,
          finished_at TEXT,
          attempts INTEGER NOT NULL DEFAULT 0,
          authoritative_sha TEXT,
          last_error TEXT,
          result_path TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY,
          timestamp TEXT NOT NULL,
          source TEXT NOT NULL,
          type TEXT NOT NULL,
          severity TEXT NOT NULL,
          phase INTEGER,
          checkpoint TEXT,
          task_id TEXT,
          title TEXT NOT NULL,
          message TEXT NOT NULL,
          metadata TEXT NOT NULL DEFAULT '{}',
          read_at TEXT,
          telegram_sent_at TEXT
        );
        CREATE TABLE IF NOT EXISTS phase_uploads (
          id TEXT PRIMARY KEY,
          phase INTEGER,
          status TEXT NOT NULL,
          upload_path TEXT NOT NULL,
          master_spec_name TEXT,
          manifest_json TEXT,
          validation_error TEXT,
          created_at TEXT NOT NULL,
          activated_at TEXT
        );
        """
    )
    # Runtime telemetry columns are additive so existing SQLite state is preserved.
    worker_columns = {row["name"] for row in con.execute("PRAGMA table_info(workers)").fetchall()}
    worker_additions = {
        "current_stage": "TEXT",
        "current_activity": "TEXT",
        "progress_pct": "INTEGER NOT NULL DEFAULT 0",
        "activity_updated_at": "TEXT",
    }
    for column, ddl in worker_additions.items():
        if column not in worker_columns:
            con.execute(f"ALTER TABLE workers ADD COLUMN {column} {ddl}")

    con.execute(
        "CREATE TABLE IF NOT EXISTS report_registry ("
        "id TEXT PRIMARY KEY,"
        "agent TEXT NOT NULL,"
        "name TEXT NOT NULL,"
        "path TEXT NOT NULL,"
        "first_seen_at TEXT NOT NULL,"
        "last_seen_at TEXT NOT NULL)"
    )

    defaults = [
        ("hermes", "backend_engineer", "WAITING"),
        ("codex", "frontend_engineer", "WAITING"),
        ("auditor", "auditor", "OFFLINE"),
        ("notifier", "notifier", "OFFLINE"),
    ]
    for wid, role, status in defaults:
        con.execute(
            "INSERT OR IGNORE INTO workers(id,role,status,last_heartbeat) VALUES(?,?,?,?)",
            (wid, role, status, now_iso()),
        )
    con.commit()
    con.close()


def emit(
    source: str,
    type_: str,
    severity: str,
    title: str,
    message: str,
    *,
    phase: int | None = None,
    checkpoint: str | None = None,
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    eid = "evt_" + uuid.uuid4().hex
    con = db()
    con.execute(
        """INSERT INTO events
        (id,timestamp,source,type,severity,phase,checkpoint,task_id,title,message,metadata)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            eid,
            now_iso(),
            source,
            type_,
            severity,
            phase,
            checkpoint,
            task_id,
            title,
            message,
            json.dumps(metadata or {}),
        ),
    )
    con.commit()
    con.close()
    return eid


def git_info(workspace: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(workspace), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()

    try:
        branch = run("branch", "--show-current")
        head = run("rev-parse", "HEAD")
        clean = run("status", "--porcelain") == ""
        return {"branch": branch, "head_sha": head, "working_tree_clean": clean}
    except Exception:
        return {"branch": None, "head_sha": None, "working_tree_clean": None}


def parse_task(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")

    def grab(key: str) -> str | None:
        m = re.search(rf"(?mi)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text)
        return m.group(1).strip() if m else None

    tid = grab("TASK_ID") or path.stem
    raw_phase = grab("PHASE")
    phase = None
    if raw_phase:
        m = re.search(r"\d+", raw_phase)
        phase = int(m.group()) if m else None
    priority = grab("PRIORITY")
    status = (grab("STATUS") or "QUEUED").upper()
    dep_match = re.search(
        r"(?ms)^\s*DEPENDENCIES\s*:\s*\n((?:\s*-\s*[^\n]+\n?)*)",
        text,
    )
    dependencies = []
    if dep_match:
        dependencies = [
            line.strip()[1:].strip()
            for line in dep_match.group(1).splitlines()
            if line.strip().startswith("-")
        ]
    return {
        "id": tid,
        "target_agent": (grab("TARGET_AGENT") or "").lower(),
        "phase": phase,
        "checkpoint": grab("CHECKPOINT"),
        "type": (grab("TYPE") or ("revision" if path.name.startswith("REV-") else "implementation")).lower(),
        "priority": int(priority) if priority and priority.isdigit() else 100,
        "status": status,
        "dependencies": dependencies,
        "authoritative_sha": grab("AUTHORITATIVE_SHA") or grab("AUDITED_SHA"),
        "text": text,
    }


def register_task(path: Path, agent: str) -> dict[str, Any]:
    meta = parse_task(path)
    if meta["target_agent"] and meta["target_agent"] != agent:
        raise ValueError(f"Task {path.name} targets {meta['target_agent']}, not {agent}")
    con = db()
    row = con.execute("SELECT * FROM tasks WHERE id=?", (meta["id"],)).fetchone()
    if not row:
        con.execute(
            """INSERT INTO tasks
            (id,target_agent,phase,checkpoint,type,priority,state,task_path,created_at,authoritative_sha)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                meta["id"],
                agent,
                meta["phase"],
                meta["checkpoint"],
                meta["type"],
                meta["priority"],
                meta["status"],
                str(path),
                now_iso(),
                meta["authoritative_sha"],
            ),
        )
        con.commit()
        emit(
            "orchestrator",
            "task.queued",
            "INFO",
            f"Task queued for {agent}",
            meta["id"],
            phase=meta["phase"],
            checkpoint=meta["checkpoint"],
            task_id=meta["id"],
        )
    row = con.execute("SELECT * FROM tasks WHERE id=?", (meta["id"],)).fetchone()
    con.close()
    return dict(row)


def update_worker(worker: str, **fields: Any) -> None:
    fields["last_heartbeat"] = now_iso()
    con = db()
    keys = list(fields)
    values = [fields[k] for k in keys]
    con.execute(
        f"UPDATE workers SET {', '.join(k + '=?' for k in keys)} WHERE id=?",
        (*values, worker),
    )
    con.commit()
    con.close()


def current_phase() -> int:
    try:
        data = yaml.safe_load((ROOT / "phase.yaml").read_text()) or {}
        return int(data.get("current_phase", 2))
    except Exception:
        return 2


def assemble_prompt(agent: str, task_path: Path) -> str:
    phase = current_phase()
    parts: list[str] = []

    def add(title: str, path: Path) -> None:
        if path.exists():
            parts.append(f"\n\n===== {title}: {path} =====\n" + path.read_text(encoding="utf-8"))

    add("GLOBAL PROJECT RULES", ROOT / "policies/PROJECT_RULES.md")
    add(
        f"{agent.upper()} ROLE RULES",
        ROOT / "policies" / ("HERMES_RULES.md" if agent == "hermes" else "CODEX_RULES.md"),
    )
    add("PROJECT MASTER PLAN", ROOT / "knowledge/PROJECT_MASTER_PLAN.md")
    add("PHASE 1 BASELINE", ROOT / "knowledge/PHASE1_BASELINE.md")
    add(
        f"PHASE {phase} MASTER SPEC",
        ROOT / "knowledge/phases" / f"PHASE{phase}_MASTER_SPEC.md",
    )
    add("BUSINESS DECISIONS", ROOT / "knowledge/BUSINESS_DECISIONS.md")

    if agent == "hermes":
        add("CURRENT HERMES HANDOFF", BACKEND_WORKSPACE / "docs/agent/HERMES_HANDOFF.md")
    else:
        for candidate in (
            FRONTEND_WORKSPACE / "docs/agent/CODEX_HANDOFF.md",
            FRONTEND_WORKSPACE / "docs/reports/codex-p2b-service-catalog-frontend.md",
        ):
            if candidate.exists():
                add("CURRENT CODEX HANDOFF", candidate)
                break

    add("ACTIVE TASK", task_path)
    parts.append(
        "\n\n===== EXECUTION DIRECTIVE =====\n"
        "Work autonomously within the standing rules. Do not ask routine approval questions. "
        "Preserve WIP on failure. Finish only when the task is READY_FOR_AUDIT or genuinely BLOCKED. "
        "Never start an unqueued later phase/checkpoint.\n"
    )
    return "".join(parts)
