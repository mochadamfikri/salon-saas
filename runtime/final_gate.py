from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from common import BACKEND_WORKSPACE, FRONTEND_WORKSPACE, db, emit, init_db, now_iso

POLL = int(os.environ.get("FINAL_GATE_POLL_SECONDS", "10"))
WORKER_ID = "final-reviewer"


def ensure_schema() -> None:
    con = db()
    con.execute(
        "INSERT OR IGNORE INTO workers(id,role,status,last_heartbeat,current_stage,current_activity,progress_pct) "
        "VALUES(?,?,?,?,?,?,?)",
        (WORKER_ID, "final_reviewer", "WAITING", now_iso(), "Menunggu kandidat", "Menunggu PASS_CANDIDATE", 0),
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS final_reviews ("
        "review_key TEXT PRIMARY KEY,"
        "phase INTEGER NOT NULL,"
        "checkpoint TEXT NOT NULL,"
        "source_agent TEXT NOT NULL,"
        "authoritative_sha TEXT NOT NULL,"
        "audit_task_id TEXT NOT NULL,"
        "verdict TEXT NOT NULL,"
        "reviewer TEXT NOT NULL,"
        "reviewed_at TEXT NOT NULL,"
        "summary TEXT NOT NULL,"
        "findings_json TEXT NOT NULL DEFAULT '[]',"
        "payload_json TEXT NOT NULL,"
        "synced_at TEXT NOT NULL,"
        "applied_at TEXT)"
    )
    con.commit()
    con.close()


def update_worker(**fields: Any) -> None:
    fields["last_heartbeat"] = now_iso()
    con = db()
    keys = list(fields)
    con.execute(
        f"UPDATE workers SET {', '.join(k + '=?' for k in keys)} WHERE id=?",
        (*[fields[k] for k in keys], WORKER_ID),
    )
    con.commit()
    con.close()


def parse_field(text: str, key: str) -> str | None:
    m = re.search(rf"(?mi)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text)
    return m.group(1).strip() if m else None


def git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def validate(audit: dict[str, Any]) -> tuple[bool, str, str, str]:
    sha = str(audit["authoritative_sha"] or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return False, "Authoritative SHA tidak valid.", "", ""

    report_path = Path(str(audit["result_path"] or ""))
    if not report_path.exists():
        return False, "Audit report tidak ditemukan.", "", ""

    report = report_path.read_text(encoding="utf-8", errors="replace")
    if parse_field(report, "AUDIT_VERDICT") != "PASS":
        return False, "Audit report bukan PASS.", "", ""
    if parse_field(report, "FINDINGS_COUNT") != "0":
        return False, "Audit findings bukan 0.", "", ""
    if parse_field(report, "AUDITED_SHA") != sha:
        return False, "AUDITED_SHA tidak sama dengan authoritative SHA.", "", ""

    task_path = Path(audit["task_path"])
    if not task_path.exists():
        return False, "File audit task tidak ditemukan.", "", ""

    task_text = task_path.read_text(encoding="utf-8")
    source_agent = (parse_field(task_text, "SOURCE_AGENT") or "").lower()
    branch = parse_field(task_text, "SOURCE_BRANCH") or ""
    if source_agent not in ("codex", "hermes") or not branch:
        return False, "SOURCE_AGENT/SOURCE_BRANCH audit tidak valid.", source_agent, branch

    workspace = FRONTEND_WORKSPACE if source_agent == "codex" else BACKEND_WORKSPACE
    git(workspace, "fetch", "origin", branch)
    remote = git(workspace, "rev-parse", f"origin/{branch}")
    if remote.returncode != 0:
        return False, f"origin/{branch} tidak dapat diverifikasi.", source_agent, branch
    remote_sha = remote.stdout.strip()

    if source_agent == "codex":
        if remote_sha != sha:
            return False, f"Frontend HEAD {remote_sha[:8]} != audited SHA {sha[:8]}.", source_agent, branch
    else:
        anc = git(workspace, "merge-base", "--is-ancestor", sha, f"origin/{branch}")
        if anc.returncode != 0:
            return False, f"Backend audited SHA {sha[:8]} tidak reachable.", source_agent, branch

    con = db()
    rows = con.execute(
        "SELECT state,authoritative_sha FROM tasks "
        "WHERE checkpoint=? AND target_agent=? AND id<>? ORDER BY created_at DESC",
        (audit["checkpoint"], source_agent, audit["id"]),
    ).fetchall()
    con.close()

    if not any(
        str(r["authoritative_sha"] or "") == sha
        and r["state"] in ("READY_FOR_AUDIT", "COMPLETED", "FINAL_PASS")
        for r in rows
    ):
        return False, "Source task pada SHA yang sama tidak ditemukan.", source_agent, branch

    return True, "Semua bukti final review valid.", source_agent, branch


def approve(audit: dict[str, Any], source_agent: str, branch: str) -> None:
    sha = str(audit["authoritative_sha"])
    checkpoint = str(audit["checkpoint"])
    phase = int(audit["phase"])
    reviewed_at = now_iso()
    summary = (
        f"Autonomous final gate approved {checkpoint} at {sha[:8]}: "
        "PASS_CANDIDATE, zero findings, exact SHA match, and source-branch proof valid."
    )
    payload = {
        "schema_version": 1,
        "checkpoint": checkpoint,
        "phase": phase,
        "source_agent": source_agent,
        "authoritative_sha": sha,
        "audit_task_id": audit["id"],
        "verdict": "FINAL_PASS",
        "reviewer": "IDSE Autonomous Final Gate v1",
        "reviewed_at": reviewed_at,
        "summary": summary,
        "findings": [],
        "source_branch": branch,
    }

    con = db()
    con.execute(
        "UPDATE tasks SET state='FINAL_PASS',finished_at=?,last_error=NULL "
        "WHERE id=? AND state='PASS_CANDIDATE' AND authoritative_sha=?",
        (reviewed_at, audit["id"], sha),
    )
    changed = con.total_changes > 0
    con.execute(
        "INSERT INTO final_reviews("
        "review_key,phase,checkpoint,source_agent,authoritative_sha,audit_task_id,"
        "verdict,reviewer,reviewed_at,summary,findings_json,payload_json,synced_at,applied_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(review_key) DO UPDATE SET "
        "verdict=excluded.verdict,reviewer=excluded.reviewer,reviewed_at=excluded.reviewed_at,"
        "summary=excluded.summary,findings_json=excluded.findings_json,"
        "payload_json=excluded.payload_json,synced_at=excluded.synced_at,applied_at=excluded.applied_at",
        (
            f"{checkpoint}:{sha}", phase, checkpoint, source_agent, sha, audit["id"],
            "FINAL_PASS", payload["reviewer"], reviewed_at, summary, "[]",
            json.dumps(payload, ensure_ascii=False, sort_keys=True), reviewed_at, reviewed_at,
        ),
    )
    con.commit()
    con.close()

    update_worker(
        status="WAITING",
        current_task_id=None,
        phase=phase,
        checkpoint=checkpoint,
        branch=branch,
        head_sha=sha,
        current_stage="Final review selesai",
        current_activity=f"{checkpoint} FINAL_PASS; menunggu kandidat berikutnya",
        progress_pct=100,
        last_successful_checkpoint=checkpoint,
    )

    if changed:
        emit(
            "final-reviewer",
            "final_review.auto_pass",
            "SUCCESS",
            f"Final Review: {checkpoint} → FINAL_PASS",
            f"{sha[:8]} lulus final gate otomatis dengan 0 findings.",
            phase=phase,
            checkpoint=checkpoint,
            task_id=audit["id"],
            metadata={"authoritative_sha": sha, "source_agent": source_agent, "source_branch": branch},
        )


def process() -> None:
    con = db()
    rows = [
        dict(r)
        for r in con.execute(
            "SELECT * FROM tasks WHERE target_agent='auditor' "
            "AND state='PASS_CANDIDATE' ORDER BY finished_at,created_at"
        ).fetchall()
    ]
    con.close()

    if not rows:
        update_worker(
            status="WAITING",
            current_task_id=None,
            current_stage="Menunggu kandidat",
            current_activity="Menunggu PASS_CANDIDATE yang eligible",
            progress_pct=0,
        )
        return

    for audit in rows:
        sha = str(audit["authoritative_sha"] or "")
        update_worker(
            status="RUNNING",
            current_task_id=audit["id"],
            phase=audit["phase"],
            checkpoint=audit["checkpoint"],
            head_sha=sha,
            current_stage="Final review",
            current_activity="Memverifikasi audit, SHA, source task, dan branch",
            progress_pct=50,
        )
        ok, reason, source_agent, branch = validate(audit)
        if ok:
            approve(audit, source_agent, branch)
            continue

        update_worker(
            status="BLOCKED",
            current_task_id=audit["id"],
            phase=audit["phase"],
            checkpoint=audit["checkpoint"],
            head_sha=sha,
            current_stage="Butuh review Owner",
            current_activity=reason,
            progress_pct=100,
        )
        emit(
            "final-reviewer",
            "final_review.owner_required",
            "OWNER_ACTION_REQUIRED",
            f"Final Review tertahan: {audit['checkpoint']}",
            reason,
            phase=audit["phase"],
            checkpoint=audit["checkpoint"],
            task_id=audit["id"],
            metadata={"authoritative_sha": sha},
        )


def main() -> None:
    init_db()
    ensure_schema()
    emit(
        "final-reviewer",
        "final_gate.online",
        "INFO",
        "Autonomous Final Gate online",
        "Final review otomatis aktif dengan hard safety rules.",
    )
    while True:
        try:
            process()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            update_worker(
                status="ERROR",
                current_stage="Error",
                current_activity=str(exc),
                progress_pct=100,
            )
            emit(
                "final-reviewer",
                "final_gate.error",
                "CRITICAL",
                "Autonomous Final Gate error",
                str(exc),
            )
        time.sleep(POLL)


if __name__ == "__main__":
    main()
