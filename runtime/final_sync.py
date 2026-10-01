from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import time
import traceback
from pathlib import Path
from typing import Any

from common import ROOT, db, emit, init_db, now_iso, register_task

POLL = int(os.environ.get("FINAL_REVIEW_SYNC_POLL_SECONDS", "30"))
SYNC_REPO = Path(os.environ.get("SALON_SYNC_REPO", "/home/ubuntu/salon-orchestrator-sync"))
LOCK = Path("/tmp/salon-orchestrator-git-sync.lock")


def log(line: str) -> None:
    path = ROOT / "runtime/logs/final-sync.log"
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


def ensure_table() -> None:
    con = db()
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


def read_remote_reviews() -> list[tuple[str, dict[str, Any]]]:
    LOCK.touch(exist_ok=True)
    with LOCK.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        git("fetch", "origin", "orchestration")
        listing = git(
            "ls-tree",
            "-r",
            "--name-only",
            "origin/orchestration",
            "state/final-reviews",
            check=False,
        )
        items: list[tuple[str, dict[str, Any]]] = []
        for path in listing.stdout.splitlines():
            path = path.strip()
            if not path.endswith(".json"):
                continue
            raw = git("show", f"origin/orchestration:{path}", check=False)
            if raw.returncode != 0:
                continue
            try:
                items.append((path, json.loads(raw.stdout)))
            except json.JSONDecodeError:
                log(f"Invalid final-review JSON: {path}")
        return items


def validate_review(payload: dict[str, Any]) -> None:
    required = (
        "schema_version",
        "checkpoint",
        "phase",
        "source_agent",
        "authoritative_sha",
        "audit_task_id",
        "verdict",
        "reviewer",
        "reviewed_at",
        "summary",
        "findings",
    )
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError("missing fields: " + ", ".join(missing))
    if payload["verdict"] not in ("FINAL_PASS", "REVISE", "BLOCKED"):
        raise ValueError("invalid verdict")
    if payload["source_agent"] not in ("hermes", "codex"):
        raise ValueError("invalid source_agent")
    if not re.fullmatch(r"[0-9a-f]{7,40}", str(payload["authoritative_sha"])):
        raise ValueError("invalid authoritative_sha")
    if not isinstance(payload["findings"], list):
        raise ValueError("findings must be a list")


def review_key(payload: dict[str, Any]) -> str:
    return f"{payload['checkpoint']}:{payload['authoritative_sha']}"


def queue_final_revision(payload: dict[str, Any]) -> str:
    checkpoint = str(payload["checkpoint"])
    sha = str(payload["authoritative_sha"])
    agent = str(payload["source_agent"])
    task_id = f"REV-FINAL-{checkpoint}-{sha[:8]}"
    path = ROOT / "inbox" / agent / f"{task_id}.md"

    findings = payload.get("findings") or []
    lines = [
        f"TARGET_AGENT: {agent.upper()}",
        f"TASK_ID: {task_id}",
        f"PHASE: {payload['phase']}",
        f"CHECKPOINT: {checkpoint}",
        "TYPE: revision",
        "PRIORITY: 3",
        f"AUTHORITATIVE_SHA: {sha}",
        f"SOURCE_AUDIT_TASK: {payload['audit_task_id']}",
        "STATUS: QUEUED",
        "",
        "ChatGPT FINAL REVIEW returned REVISE.",
        "",
        "SUMMARY:",
        str(payload.get("summary") or ""),
        "",
        "FINDINGS:",
    ]
    if findings:
        for i, finding in enumerate(findings, 1):
            if isinstance(finding, dict):
                text = (
                    finding.get("detail")
                    or finding.get("summary")
                    or json.dumps(finding, ensure_ascii=False)
                )
            else:
                text = str(finding)
            lines.append(f"{i}. {text}")
    else:
        lines.append("No structured findings supplied; inspect the final-review summary.")

    lines += [
        "",
        "Fix the final-review findings only. Preserve compatible later work.",
        "Run required tests/quality gates, commit, push, update completion/handoff reports,",
        "and stop READY_FOR_AUDIT. Do not merge or deploy.",
        "",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("\n".join(lines), encoding="utf-8")
    register_task(path, agent)
    return task_id


def apply_review(path: str, payload: dict[str, Any]) -> None:
    validate_review(payload)
    ensure_table()

    key = review_key(payload)
    verdict = str(payload["verdict"])
    audit_task_id = str(payload["audit_task_id"])
    sha = str(payload["authoritative_sha"])
    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    con = db()
    existing = con.execute(
        "SELECT payload_json,applied_at FROM final_reviews WHERE review_key=?",
        (key,),
    ).fetchone()
    changed = not existing or existing["payload_json"] != payload_text

    con.execute(
        "INSERT INTO final_reviews "
        "(review_key,phase,checkpoint,source_agent,authoritative_sha,audit_task_id,"
        "verdict,reviewer,reviewed_at,summary,findings_json,payload_json,synced_at,applied_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(review_key) DO UPDATE SET "
        "phase=excluded.phase,checkpoint=excluded.checkpoint,source_agent=excluded.source_agent,"
        "audit_task_id=excluded.audit_task_id,verdict=excluded.verdict,reviewer=excluded.reviewer,"
        "reviewed_at=excluded.reviewed_at,summary=excluded.summary,"
        "findings_json=excluded.findings_json,payload_json=excluded.payload_json,"
        "synced_at=excluded.synced_at",
        (
            key,
            int(payload["phase"]),
            str(payload["checkpoint"]),
            str(payload["source_agent"]),
            sha,
            audit_task_id,
            verdict,
            str(payload["reviewer"]),
            str(payload["reviewed_at"]),
            str(payload["summary"]),
            json.dumps(payload.get("findings") or [], ensure_ascii=False),
            payload_text,
            now_iso(),
            existing["applied_at"] if existing else None,
        ),
    )

    audit = con.execute(
        "SELECT authoritative_sha FROM tasks WHERE id=?",
        (audit_task_id,),
    ).fetchone()
    if audit and str(audit["authoritative_sha"] or "").startswith(sha[:8]):
        mapped = {
            "FINAL_PASS": "FINAL_PASS",
            "REVISE": "REVISE_REQUIRED",
            "BLOCKED": "BLOCKED",
        }[verdict]
        con.execute(
            "UPDATE tasks SET state=?,finished_at=? WHERE id=?",
            (mapped, now_iso(), audit_task_id),
        )

    con.commit()
    con.close()

    if not changed:
        return

    revision_task = None
    if verdict == "REVISE":
        revision_task = queue_final_revision(payload)

    con = db()
    con.execute(
        "UPDATE final_reviews SET applied_at=? WHERE review_key=?",
        (now_iso(), key),
    )
    con.commit()
    con.close()

    severity = {
        "FINAL_PASS": "SUCCESS",
        "REVISE": "WARNING",
        "BLOCKED": "OWNER_ACTION_REQUIRED",
    }[verdict]

    message = str(payload.get("summary") or "")
    if revision_task:
        message += f" Revision task queued: {revision_task}."

    emit(
        "final-review",
        "final_review.synced",
        severity,
        f"ChatGPT Final Review: {payload['checkpoint']} → {verdict}",
        message,
        phase=int(payload["phase"]),
        checkpoint=str(payload["checkpoint"]),
        task_id=audit_task_id,
        metadata={
            "authoritative_sha": sha,
            "verdict": verdict,
            "github_path": path,
            "revision_task": revision_task,
        },
    )
    log(f"Applied {path}: {verdict}")


def main() -> None:
    init_db()
    ensure_table()
    emit(
        "final-review",
        "final_review_sync.online",
        "INFO",
        "Final Review Sync online",
        "Watching GitHub for ChatGPT final reviews",
    )
    while True:
        try:
            for path, payload in read_remote_reviews():
                try:
                    apply_review(path, payload)
                except Exception as exc:
                    log(f"Failed {path}: {exc}")
        except KeyboardInterrupt:
            break
        except Exception as exc:
            log("ERROR " + repr(exc) + " | " + traceback.format_exc()[-2000:])
            emit(
                "final-review",
                "final_review_sync.error",
                "CRITICAL",
                "Final Review Sync error",
                str(exc),
            )
        time.sleep(POLL)


if __name__ == "__main__":
    main()
