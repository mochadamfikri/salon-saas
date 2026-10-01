from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import traceback
from pathlib import Path
from typing import Any

from common import (
    BACKEND_WORKSPACE,
    FRONTEND_WORKSPACE,
    ROOT,
    db,
    emit,
    git_info,
    init_db,
    now_iso,
    parse_task,
    register_task,
    update_worker,
)

POLL = int(os.environ.get("AUDITOR_POLL_SECONDS", "30"))
AUDITOR_BIN = os.environ.get("AUDITOR_BIN") or os.environ.get("CODEX_BIN", "codex")
AUDITOR_CODEX_HOME = os.environ.get("AUDITOR_CODEX_HOME") or os.environ.get("CODEX_HOME", "/home/ubuntu/.codex-muse")


def log(line: str) -> None:
    path = ROOT / "runtime/logs/auditor.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {line}\n")
    update_worker("auditor", last_log=line[-500:])


def grab(text: str, key: str) -> str | None:
    m = re.search(rf"(?mi)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text)
    return m.group(1).strip() if m else None


def task_meta(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    base = parse_task(path)
    return {
        **base,
        "text": text,
        "source_agent": (grab(text, "SOURCE_AGENT") or "hermes").lower(),
        "source_branch": grab(text, "SOURCE_BRANCH"),
        "base_sha": grab(text, "BASE_SHA") or grab(text, "AUDIT_BASE_SHA"),
        "audited_sha": row.get("authoritative_sha") or grab(text, "AUDITED_SHA"),
        "depends_on": grab(text, "DEPENDS_ON"),
        "report_source": grab(text, "REPORT_SOURCE"),
    }


def task_row(task_id: str) -> dict[str, Any] | None:
    con = db()
    row = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def set_task(task_id: str, **fields: Any) -> None:
    con = db()
    keys = list(fields)
    con.execute(
        f"UPDATE tasks SET {', '.join(k + '=?' for k in keys)} WHERE id=?",
        (*[fields[k] for k in keys], task_id),
    )
    con.commit()
    con.close()


def scan() -> list[tuple[int, str, Path, dict[str, Any]]]:
    inbox = ROOT / "inbox/auditor"
    inbox.mkdir(parents=True, exist_ok=True)
    found: list[tuple[int, str, Path, dict[str, Any]]] = []
    for path in inbox.glob("*.md"):
        try:
            row = register_task(path, "auditor")
            if row["state"] not in ("QUEUED", "WAITING_DEPENDENCY"):
                continue
            meta = task_meta(path, row)
            dep = meta["depends_on"]
            if dep:
                dep_row = task_row(dep)
                if not dep_row or dep_row["state"] not in ("PASS_CANDIDATE", "FINAL_PASS"):
                    if row["state"] != "WAITING_DEPENDENCY":
                        set_task(row["id"], state="WAITING_DEPENDENCY")
                    continue
                if row["state"] == "WAITING_DEPENDENCY":
                    set_task(row["id"], state="QUEUED")
                    row = task_row(row["id"]) or row
            found.append((row["priority"], row["created_at"], path, row))
        except Exception as exc:
            log(f"Invalid audit task {path.name}: {exc}")
    found.sort(key=lambda x: (x[0], x[1]))
    return found


def source_workspace(agent: str) -> Path:
    if agent == "hermes":
        return BACKEND_WORKSPACE
    if agent == "codex":
        return FRONTEND_WORKSPACE
    raise ValueError(f"unsupported source agent: {agent}")


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def ensure_commit(repo: Path, sha: str) -> None:
    git("fetch", "origin", cwd=repo, check=False)
    p = git("cat-file", "-e", f"{sha}^{{commit}}", cwd=repo, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"commit not found: {sha}; {p.stdout[-500:]}")


def audit_worktree(task_id: str, repo: Path, sha: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", task_id)[:80]
    root = ROOT / "runtime/audit-worktrees"
    root.mkdir(parents=True, exist_ok=True)
    path = root / safe
    if path.exists():
        git("worktree", "remove", "--force", str(path), cwd=repo, check=False)
        shutil.rmtree(path, ignore_errors=True)
    ensure_commit(repo, sha)
    p = git("worktree", "add", "--detach", str(path), sha, cwd=repo, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {p.stdout[-1000:]}")
    return path


def cleanup_worktree(repo: Path, path: Path) -> None:
    git("worktree", "remove", "--force", str(path), cwd=repo, check=False)
    shutil.rmtree(path, ignore_errors=True)


def read_if(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_prompt(meta: dict[str, Any], worktree: Path) -> str:
    phase = meta.get("phase") or 2
    source_report = ""
    if meta.get("report_source"):
        source_report = read_if(worktree / str(meta["report_source"]))
    base_sha = meta.get("base_sha") or ""
    audited_sha = meta.get("audited_sha") or ""
    return f"""You are the independent Salon SaaS automated engineering auditor.

===== GLOBAL PROJECT RULES =====
{read_if(ROOT / 'policies/PROJECT_RULES.md')}

===== AUDITOR RULES =====
{read_if(ROOT / 'policies/AUDITOR_RULES.md')}

===== BUSINESS DECISIONS =====
{read_if(ROOT / 'knowledge/BUSINESS_DECISIONS.md')}

===== PHASE {phase} MASTER SPEC =====
{read_if(ROOT / 'knowledge/phases' / f'PHASE{phase}_MASTER_SPEC.md')}

===== AUDIT TASK =====
{meta['text']}

===== IMPLEMENTATION COMPLETION REPORT (UNTRUSTED EVIDENCE) =====
{source_report or '(not supplied)'}

AUDIT EXECUTION REQUIREMENTS:
- The disposable audit worktree is: {worktree}
- It is pinned to AUDITED_SHA {audited_sha}.
- BASE_SHA is {base_sha or '(not supplied)'}. If supplied, inspect `git diff {base_sha}..{audited_sha}` and the relevant files/tests.
- Do not rely on the completion report as proof.
- Inspect actual implementation and tests for checkpoint {meta.get('checkpoint') or '(unknown)'}.
- Run targeted tests plus broader regression/quality gates when feasible.
- Do NOT implement fixes. Do NOT commit/push/merge/deploy.
- Temporary/cache files inside this disposable worktree are allowed.
- If verification is prevented by environment/tooling, distinguish that from an implementation defect and use BLOCKED when evidence is insufficient.
- Finish with the exact three machine-readable lines required by AUDITOR_RULES.md.
"""


def parse_verdict(text: str, audited_sha: str) -> tuple[str, int]:
    m = re.search(r"(?mi)^AUDIT_VERDICT:\s*(PASS|REVISE|BLOCKED)\s*$", text)
    if not m:
        return "BLOCKED", 0
    verdict = m.group(1).upper()
    sha_m = re.search(r"(?mi)^AUDITED_SHA:\s*([0-9a-f]{7,40})\s*$", text)
    if not sha_m or not audited_sha.startswith(sha_m.group(1)) and not sha_m.group(1).startswith(audited_sha[:7]):
        return "BLOCKED", 0
    count_m = re.search(r"(?mi)^FINDINGS_COUNT:\s*(\d+)\s*$", text)
    return verdict, int(count_m.group(1)) if count_m else 0


def revision_task(meta: dict[str, Any], report_path: Path, report: str) -> tuple[str, Path]:
    source = meta["source_agent"]
    checkpoint = meta.get("checkpoint") or "UNKNOWN"
    audited_sha = str(meta.get("audited_sha") or "unknown")
    task_id = f"REV-{checkpoint}-{audited_sha[:8]}"
    target = ROOT / "inbox" / source / f"{task_id}.md"
    body = f"""TARGET_AGENT: {source.upper()}
TASK_ID: {task_id}
PHASE: {meta.get('phase') or 2}
CHECKPOINT: {checkpoint}
TYPE: revision
PRIORITY: 5
AUTHORITATIVE_SHA: {audited_sha}
AUDIT_BASE_SHA: {meta.get('base_sha') or ''}
SOURCE_AUDIT_TASK: {meta.get('id') or ''}
AUDIT_REPORT: {report_path}
STATUS: QUEUED

Fix every blocking finding in the audit report below. Work on the current engineering branch, preserve later compatible work, run the required regression/quality gates, commit, push, update the completion/handoff report, then stop READY_FOR_AUDIT. Do not merge, deploy, change production, or invent business rules.

===== AUDIT REPORT =====
{report}
"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return task_id, target


def maybe_requeue_revisions() -> None:
    con = db()
    audits = con.execute(
        "SELECT * FROM tasks WHERE target_agent='auditor' AND state='REVISE_REQUIRED'"
    ).fetchall()
    for audit in audits:
        marker = audit["last_error"] or ""
        m = re.search(r"REVISION_TASK_ID=([^;\s]+)", marker)
        if not m:
            continue
        rev_id = m.group(1)
        rev = con.execute("SELECT * FROM tasks WHERE id=?", (rev_id,)).fetchone()
        if not rev or rev["state"] != "READY_FOR_AUDIT":
            continue
        src = rev["target_agent"]
        worker = con.execute("SELECT head_sha FROM workers WHERE id=?", (src,)).fetchone()
        new_sha = worker["head_sha"] if worker and worker["head_sha"] else None
        if not new_sha:
            continue
        con.execute(
            "UPDATE tasks SET state='QUEUED',authoritative_sha=?,last_error=NULL WHERE id=?",
            (new_sha, audit["id"]),
        )
        con.commit()
        emit(
            "auditor",
            "audit.requeued",
            "INFO",
            f"Re-audit queued for {audit['checkpoint']}",
            f"Revision {rev_id} is READY_FOR_AUDIT at {new_sha[:8]}",
            phase=audit["phase"],
            checkpoint=audit["checkpoint"],
            task_id=audit["id"],
        )
    con.close()


def mark_revision_complete(audit_task_id: str) -> None:
    con = db()
    row = con.execute("SELECT last_error FROM tasks WHERE id=?", (audit_task_id,)).fetchone()
    marker = row["last_error"] if row else None
    if marker:
        m = re.search(r"REVISION_TASK_ID=([^;\s]+)", marker)
        if m:
            con.execute(
                "UPDATE tasks SET state='COMPLETED',finished_at=COALESCE(finished_at,?) WHERE id=?",
                (now_iso(), m.group(1)),
            )
            con.commit()
    con.close()


def run_audit(path: Path, row: dict[str, Any]) -> None:
    meta = task_meta(path, row)
    meta["id"] = row["id"]
    source = meta["source_agent"]
    repo = source_workspace(source)
    audited_sha = str(meta.get("audited_sha") or "").strip()
    if not audited_sha:
        raise RuntimeError(f"{row['id']} has no AUDITED_SHA/authoritative_sha")

    attempts = int(row["attempts"] or 0) + 1
    set_task(row["id"], state="RUNNING", started_at=row["started_at"] or now_iso(), attempts=attempts)
    update_worker(
        "auditor",
        status="AUDITING",
        current_task_id=row["id"],
        phase=row["phase"],
        checkpoint=row["checkpoint"],
        head_sha=audited_sha,
        branch=meta.get("source_branch"),
        task_started_at=now_iso(),
        retry_attempt=attempts - 1,
    )
    emit(
        "auditor",
        "audit.started",
        "INFO",
        f"Audit started: {row['checkpoint']}",
        f"Auditing {source} at {audited_sha[:8]}",
        phase=row["phase"],
        checkpoint=row["checkpoint"],
        task_id=row["id"],
    )
    log(f"START {row['id']} sha={audited_sha}")

    worktree: Path | None = None
    try:
        worktree = audit_worktree(row["id"], repo, audited_sha)
        prompt = build_prompt(meta, worktree)
        prompt_dir = ROOT / "runtime/prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompt_dir / f"{row['id']}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        result_dir = ROOT / "runtime/results"
        result_dir.mkdir(parents=True, exist_ok=True)
        result_path = result_dir / f"{row['id']}.audit.md"

        env = os.environ.copy()
        env["CODEX_HOME"] = AUDITOR_CODEX_HOME
        cmd = [
            AUDITOR_BIN,
            "--ask-for-approval",
            "never",
            "--sandbox",
            "workspace-write",
            "exec",
            "--cd",
            str(worktree),
            "--json",
            "-o",
            str(result_path),
            "-",
        ]
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            cwd=worktree,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = proc.stdout or ""
        report = result_path.read_text(encoding="utf-8", errors="replace") if result_path.exists() else output
        if proc.returncode != 0:
            report += f"\n\nAUDITOR PROCESS EXIT: {proc.returncode}\n\n{output[-3000:]}"
        verdict, findings = parse_verdict(report, audited_sha)
        if proc.returncode != 0:
            verdict = "BLOCKED"

        report_dir = ROOT / "audit" / source
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"AUDIT-{row['checkpoint']}-{audited_sha[:8]}.md"
        header = (
            f"# Automated Audit — {row['checkpoint']}\n\n"
            f"- Source agent: {source}\n"
            f"- Source branch: {meta.get('source_branch') or '(unspecified)'}\n"
            f"- Base SHA: {meta.get('base_sha') or '(unspecified)'}\n"
            f"- Audited SHA: {audited_sha}\n"
            f"- Generated: {now_iso()}\n\n"
        )
        report_path.write_text(header + report, encoding="utf-8")

        if verdict == "PASS":
            previous_marker = row.get("last_error")
            set_task(
                row["id"],
                state="PASS_CANDIDATE",
                finished_at=now_iso(),
                result_path=str(report_path),
                last_error=previous_marker,
            )
            if previous_marker:
                mark_revision_complete(row["id"])
            update_worker(
                "auditor",
                status="WAITING",
                current_task_id=None,
                head_sha=audited_sha,
                last_exit_code=0,
                last_successful_checkpoint=row["checkpoint"],
            )
            emit(
                "auditor",
                "audit.pass",
                "SUCCESS",
                f"Audit candidate PASS: {row['checkpoint']}",
                f"{audited_sha[:8]} passed automated pre-audit. Awaiting ChatGPT FINAL PASS. Findings: {findings}",
                phase=row["phase"],
                checkpoint=row["checkpoint"],
                task_id=row["id"],
                metadata={"audited_sha": audited_sha, "report": str(report_path)},
            )
        elif verdict == "REVISE":
            rev_id, rev_path = revision_task(meta, report_path, report)
            # register immediately so the panel shows it without waiting for Hermes scan
            register_task(rev_path, source)
            set_task(
                row["id"],
                state="REVISE_REQUIRED",
                finished_at=now_iso(),
                result_path=str(report_path),
                last_error=f"REVISION_TASK_ID={rev_id}",
            )
            update_worker("auditor", status="WAITING_REVISION", current_task_id=row["id"], last_exit_code=0)
            emit(
                "auditor",
                "audit.revise",
                "WARNING",
                f"Revision required: {row['checkpoint']}",
                f"{findings} finding(s). {rev_id} queued automatically for {source}.",
                phase=row["phase"],
                checkpoint=row["checkpoint"],
                task_id=row["id"],
                metadata={"revision_task": rev_id, "report": str(report_path)},
            )
        else:
            set_task(
                row["id"],
                state="BLOCKED",
                finished_at=now_iso(),
                result_path=str(report_path),
                last_error="Automated auditor could not produce a reliable PASS/REVISE verdict",
            )
            update_worker("auditor", status="BLOCKED", current_task_id=row["id"], last_exit_code=proc.returncode)
            emit(
                "auditor",
                "audit.blocked",
                "OWNER_ACTION_REQUIRED",
                f"Audit BLOCKED: {row['checkpoint']}",
                "Audit evidence was insufficient or the auditor process failed. Open the audit report in Reports.",
                phase=row["phase"],
                checkpoint=row["checkpoint"],
                task_id=row["id"],
                metadata={"report": str(report_path)},
            )
        log(f"DONE {row['id']} verdict={verdict} report={report_path}")
    finally:
        if worktree is not None:
            cleanup_worktree(repo, worktree)


def main() -> None:
    init_db()
    update_worker("auditor", status="WAITING")
    emit("auditor", "worker.online", "INFO", "Auditor worker online", "Independent audit worker started")
    while True:
        try:
            maybe_requeue_revisions()
            tasks = scan()
            if not tasks:
                update_worker("auditor", status="WAITING", current_task_id=None)
                time.sleep(POLL)
                continue
            _, _, path, row = tasks[0]
            run_audit(path, row)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            log("AUDITOR ERROR " + repr(exc) + " | " + traceback.format_exc()[-2500:])
            update_worker("auditor", status="ERROR")
            emit("auditor", "worker.error", "CRITICAL", "Auditor worker error", str(exc))
            time.sleep(15)


if __name__ == "__main__":
    main()
