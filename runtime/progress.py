from __future__ import annotations

import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Mapping

from common import now_iso, update_worker


def infer_activity(line: str) -> tuple[str, str, int] | None:
    """Map observable process output to a safe operational stage.
    Never stores or exposes raw model reasoning.
    """
    low = line.lower()

    rules = [
        (("handoff", "completion report", "audit report", "report.md"), "Reporting", "Menyiapkan report / handoff", 96),
        (("git push", "pushing", "pushed"), "Publishing", "Push perubahan ke remote", 92),
        (("git commit", "committed", "commit "), "Committing", "Membuat commit", 86),
        (("ruff", "black", "eslint", "typecheck", "type check", "build", "quality gate"), "Quality gates", "Menjalankan quality gates", 80),
        (("pytest", "vitest", " test", "tests", "testing"), "Testing", "Menjalankan test", 70),
        (("patch", "edit", "write", "implement", "modify", "update file"), "Implementing", "Mengerjakan perubahan source", 48),
        (("diff", "grep", "search", "inspect", "read", "cat "), "Inspecting", "Memeriksa source / diff", 28),
        (("git status", "git fetch", "fetching"), "Repository check", "Memeriksa repository", 20),
        (("context", "prompt", "initializ"), "Loading context", "Memuat konteks task", 12),
    ]
    for needles, stage, activity, pct in rules:
        if any(n in low for n in needles):
            return stage, activity, pct
    return None


def run_streamed(
    cmd: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    worker_id: str,
    input_text: str | None = None,
    initial_stage: str = "Executing",
    initial_activity: str = "Menjalankan agent",
    initial_progress: int = 18,
) -> tuple[int, str]:
    """Run an agent while keeping worker heartbeat/progress live.

    Raw stdout is returned to the caller but is NOT copied to the worker-detail
    fields. Worker details only receive generic, inferred operational stages.
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=dict(env),
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    if input_text is not None and proc.stdin is not None:
        proc.stdin.write(input_text)
        proc.stdin.close()

    q: queue.Queue[str | None] = queue.Queue()
    output: list[str] = []

    def reader() -> None:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                q.put(line)
        finally:
            q.put(None)

    threading.Thread(target=reader, daemon=True).start()

    stage = initial_stage
    activity = initial_activity
    progress = initial_progress
    stream_done = False
    last_heartbeat = 0.0

    update_worker(
        worker_id,
        current_stage=stage,
        current_activity=activity,
        progress_pct=progress,
        activity_updated_at=now_iso(),
    )

    while True:
        try:
            item = q.get(timeout=0.75)
            if item is None:
                stream_done = True
            else:
                output.append(item)
                inferred = infer_activity(item)
                if inferred:
                    new_stage, new_activity, new_progress = inferred
                    new_progress = max(progress, new_progress)
                    if (new_stage, new_activity, new_progress) != (stage, activity, progress):
                        stage, activity, progress = new_stage, new_activity, new_progress
                        update_worker(
                            worker_id,
                            current_stage=stage,
                            current_activity=activity,
                            progress_pct=progress,
                            activity_updated_at=now_iso(),
                        )
        except queue.Empty:
            pass

        now = time.monotonic()
        if now - last_heartbeat >= 3:
            update_worker(worker_id)
            last_heartbeat = now

        if proc.poll() is not None and stream_done and q.empty():
            break

    return proc.returncode or 0, "".join(output)
