from __future__ import annotations

import argparse
import os
import subprocess
import time
import traceback
from pathlib import Path

from common import (
    BACKEND_WORKSPACE,
    FRONTEND_WORKSPACE,
    ROOT,
    assemble_prompt,
    db,
    emit,
    git_info,
    init_db,
    now_iso,
    register_task,
    update_worker,
)

from progress import run_streamed

POLL = int(os.environ.get("WORKER_POLL_SECONDS", "30"))
MAX_ATTEMPTS = int(os.environ.get("WORKER_MAX_ATTEMPTS", "3"))


def log(worker: str, line: str) -> None:
    path = ROOT / "runtime/logs" / f"{worker}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {line}\n")
    update_worker(worker, last_log=line[-500:])


def scan(agent: str):
    inbox = ROOT / "inbox" / agent
    inbox.mkdir(parents=True, exist_ok=True)
    found = []
    for path in inbox.glob("*.md"):
        try:
            row = register_task(path, agent)
            if row["state"] in ("QUEUED", "REVISE"):
                found.append((row["priority"], row["created_at"], path, row))
        except Exception as exc:
            log(agent, f"Invalid task {path.name}: {exc}")
    found.sort(key=lambda x: (x[0], x[1]))
    return found


def delivery_check(workspace: Path, before: dict, after: dict) -> tuple[bool, str]:
    before_sha = before.get("head_sha")
    after_sha = after.get("head_sha")
    branch = after.get("branch")
    if not after_sha or not branch:
        return False, "HEAD/branch tidak dapat diverifikasi"
    if before_sha == after_sha:
        return False, "agent selesai tetapi tidak menghasilkan commit baru"
    if not after.get("working_tree_clean"):
        return False, "working tree masih kotor"
    try:
        remote = subprocess.check_output(
            ["git", "-C", str(workspace), "ls-remote", "origin", f"refs/heads/{branch}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        remote_sha = remote.split()[0] if remote else ""
    except Exception:
        return False, "remote branch tidak dapat diverifikasi"
    if remote_sha != after_sha:
        return False, f"commit {after_sha[:8]} belum ter-push ke origin/{branch}"
    return True, "commit baru bersih dan sudah ter-push"


def run_task(agent: str, path: Path, row: dict) -> None:
    workspace = BACKEND_WORKSPACE if agent == "hermes" else FRONTEND_WORKSPACE
    before = git_info(workspace)
    prompt = assemble_prompt(agent, path)

    prompt_dir = ROOT / "runtime/prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / f"{row['id']}.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    result_dir = ROOT / "runtime/results"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / f"{row['id']}.txt"

    attempts = row["attempts"] + 1
    con = db()
    con.execute(
        "UPDATE tasks SET state='RUNNING',started_at=COALESCE(started_at,?),attempts=?,last_error=NULL WHERE id=?",
        (now_iso(), attempts, row["id"]),
    )
    con.commit()
    con.close()

    update_worker(
        agent,
        status="RUNNING",
        current_task_id=row["id"],
        phase=row["phase"],
        checkpoint=row["checkpoint"],
        branch=before["branch"],
        head_sha=before["head_sha"],
        working_tree_clean=1 if before["working_tree_clean"] else 0,
        task_started_at=now_iso(),
        retry_attempt=attempts - 1,
        current_stage="Preparing",
        current_activity="Menyiapkan task dan workspace",
        progress_pct=8,
        activity_updated_at=now_iso(),
    )
    emit(
        agent,
        "task.started",
        "INFO",
        f"{agent.title()} started {row['id']}",
        path.name,
        phase=row["phase"],
        checkpoint=row["checkpoint"],
        task_id=row["id"],
    )
    log(agent, f"START {row['id']} attempt {attempts}/{MAX_ATTEMPTS}")

    env = os.environ.copy()
    if agent == "codex":
        env["CODEX_HOME"] = os.environ.get("CODEX_HOME", "/home/ubuntu/.codex-muse")
        cmd = [
            os.environ.get("CODEX_BIN", "codex"),
            "--ask-for-approval",
            "never",
            "--sandbox",
            "workspace-write",
            "exec",
            "--cd",
            str(workspace),
            "--json",
            "-o",
            str(result_path),
            "-",
        ]
        returncode, output = run_streamed(
            cmd,
            cwd=workspace,
            env=env,
            worker_id=agent,
            input_text=prompt,
            initial_stage="Loading context",
            initial_activity="Memuat task frontend",
            initial_progress=12,
        )
    else:
        cmd = [os.environ.get("HERMES_BIN", "hermes"), "chat", "--query-file", str(prompt_path), "--oneshot"]
        returncode, output = run_streamed(
            cmd,
            cwd=workspace,
            env=env,
            worker_id=agent,
            initial_stage="Loading context",
            initial_activity="Memuat task backend",
            initial_progress=12,
        )
        result_path.write_text(output or "", encoding="utf-8")

    summary = output[-2000:] if output else f"process exited {returncode}"
    log(agent, summary.replace("\n", " | "))

    after = git_info(workspace)
    con = db()
    delivered = False
    delivery_reason = ""
    if returncode == 0:
        delivered, delivery_reason = delivery_check(workspace, before, after)

    if returncode == 0 and delivered:
        con.execute(
            "UPDATE tasks SET state='READY_FOR_AUDIT',finished_at=?,result_path=?,last_error=NULL,authoritative_sha=? WHERE id=?",
            (now_iso(), str(result_path), after["head_sha"], row["id"]),
        )
        con.commit()
        con.close()
        update_worker(
            agent,
            status="READY_FOR_AUDIT",
            current_task_id=row["id"],
            head_sha=after["head_sha"],
            branch=after["branch"],
            working_tree_clean=1,
            last_exit_code=0,
            last_successful_checkpoint=row["checkpoint"],
            current_stage="Siap diaudit",
            current_activity="Commit baru sudah ter-push; menunggu audit",
            progress_pct=100,
            activity_updated_at=now_iso(),
        )
        emit(
            agent,
            "task.ready_for_audit",
            "SUCCESS",
            f"{agent.title()} siap diaudit",
            f"{row['id']} selesai dan ter-push. HEAD {after['head_sha'][:8]}",
            phase=row["phase"],
            checkpoint=row["checkpoint"],
            task_id=row["id"],
            metadata={"head_sha": after["head_sha"], "clean": True},
        )
        return

    if returncode == 0:
        returncode = 86
        err = f"delivery-check gagal: {delivery_reason}"
    else:
        err = f"exit={returncode}; {output[-1500:]}"
    if attempts < MAX_ATTEMPTS and returncode != 86:
        con.execute(
            "UPDATE tasks SET state='REVISE',last_error=? WHERE id=?",
            (err, row["id"]),
        )
        con.commit()
        con.close()
        update_worker(
            agent,
            status="RECOVERING",
            last_exit_code=returncode,
            retry_attempt=attempts,
        )
        emit(
            agent,
            "worker.recovering",
            "WARNING",
            f"{agent.title()} recovering",
            f"{row['id']} failed attempt {attempts}/{MAX_ATTEMPTS}; a fresh session will retry.",
            phase=row["phase"],
            checkpoint=row["checkpoint"],
            task_id=row["id"],
        )
        time.sleep(10)
    else:
        con.execute(
            "UPDATE tasks SET state='BLOCKED',finished_at=?,last_error=? WHERE id=?",
            (now_iso(), err, row["id"]),
        )
        con.commit()
        con.close()
        update_worker(
            agent,
            status="BLOCKED",
            last_exit_code=returncode,
            retry_attempt=attempts,
        )
        emit(
            agent,
            "worker.blocked",
            "OWNER_ACTION_REQUIRED",
            f"{agent.title()} blocked",
            f"{row['id']} blocked: {err}. WIP was preserved.",
            phase=row["phase"],
            checkpoint=row["checkpoint"],
            task_id=row["id"],
            metadata={"exit_code": returncode},
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", choices=["hermes", "codex"])
    args = parser.parse_args()
    agent = args.agent

    init_db()
    update_worker(agent, status="WAITING")
    emit(agent, "worker.online", "INFO", f"{agent.title()} worker online", "Worker service started")

    while True:
        try:
            con = db()
            worker = con.execute("SELECT * FROM workers WHERE id=?", (agent,)).fetchone()
            con.close()
            if worker and worker["paused"]:
                update_worker(agent, status="PAUSED")
                time.sleep(POLL)
                continue

            tasks = scan(agent)
            if not tasks:
                info = git_info(BACKEND_WORKSPACE if agent == "hermes" else FRONTEND_WORKSPACE)
                update_worker(
                    agent,
                    status="WAITING",
                    current_task_id=None,
                    branch=info["branch"],
                    head_sha=info["head_sha"],
                    working_tree_clean=1 if info["working_tree_clean"] else 0,
                    current_stage="Idle",
                    current_activity="Menunggu task",
                    progress_pct=0,
                    activity_updated_at=now_iso(),
                )
                time.sleep(POLL)
                continue

            _, _, path, row = tasks[0]
            run_task(agent, path, row)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            log(agent, "WORKER ERROR " + repr(exc) + " | " + traceback.format_exc()[-2000:])
            update_worker(agent, status="ERROR")
            emit(agent, "worker.error", "CRITICAL", f"{agent.title()} worker error", str(exc))
            time.sleep(15)


if __name__ == "__main__":
    main()
