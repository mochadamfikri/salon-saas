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
        "UPDATE tasks SET state='RUNNING',started_at=COALESCE(started_at,?),attempts=? WHERE id=?",
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
            "exec",
            "--cd",
            str(workspace),
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "never",
            "--json",
            "-o",
            str(result_path),
            "-",
        ]
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    else:
        cmd = [os.environ.get("HERMES_BIN", "hermes"), "chat", "--query-file", str(prompt_path), "--oneshot"]
        proc = subprocess.run(
            cmd,
            text=True,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        result_path.write_text(proc.stdout or "", encoding="utf-8")

    output = proc.stdout or ""
    summary = output[-2000:] if output else f"process exited {proc.returncode}"
    log(agent, summary.replace("\n", " | "))

    after = git_info(workspace)
    con = db()
    if proc.returncode == 0:
        con.execute(
            "UPDATE tasks SET state='READY_FOR_AUDIT',finished_at=?,result_path=?,last_error=NULL WHERE id=?",
            (now_iso(), str(result_path), row["id"]),
        )
        con.commit()
        con.close()
        update_worker(
            agent,
            status="READY_FOR_AUDIT",
            current_task_id=row["id"],
            head_sha=after["head_sha"],
            branch=after["branch"],
            working_tree_clean=1 if after["working_tree_clean"] else 0,
            last_exit_code=0,
            last_successful_checkpoint=row["checkpoint"],
        )
        emit(
            agent,
            "task.ready_for_audit",
            "SUCCESS",
            f"{agent.title()} ready for audit",
            f"{row['id']} finished. HEAD {after['head_sha']}",
            phase=row["phase"],
            checkpoint=row["checkpoint"],
            task_id=row["id"],
            metadata={"head_sha": after["head_sha"], "clean": after["working_tree_clean"]},
        )
        return

    err = f"exit={proc.returncode}; {output[-1500:]}"
    if attempts < MAX_ATTEMPTS:
        con.execute(
            "UPDATE tasks SET state='REVISE',last_error=? WHERE id=?",
            (err, row["id"]),
        )
        con.commit()
        con.close()
        update_worker(
            agent,
            status="RECOVERING",
            last_exit_code=proc.returncode,
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
            last_exit_code=proc.returncode,
            retry_attempt=attempts,
        )
        emit(
            agent,
            "worker.blocked",
            "OWNER_ACTION_REQUIRED",
            f"{agent.title()} blocked",
            f"{row['id']} failed after {attempts} fresh-session attempts. WIP was preserved.",
            phase=row["phase"],
            checkpoint=row["checkpoint"],
            task_id=row["id"],
            metadata={"exit_code": proc.returncode},
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
