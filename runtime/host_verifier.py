from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

BACKEND_REPO = Path(os.environ.get("HERMES_WORKSPACE", "/home/ubuntu/salon-saas"))
BACKEND_VENV = Path(os.environ.get("HERMES_VENV", str(BACKEND_REPO / ".venv")))
BACKEND_ENV = Path(os.environ.get("HERMES_ENV_FILE", str(BACKEND_REPO / ".env")))


def run(cmd: list[str], cwd: Path, timeout: int = 600) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    output = proc.stdout or ""
    # Keep only concise, non-secret command evidence. Test/tool output should not
    # contain environment values; still cap it defensively.
    tail = output[-4000:]
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "duration_seconds": round(time.monotonic() - started, 2),
        "output_tail": tail,
    }


def verify_backend_sha(sha: str) -> dict[str, Any]:
    if not BACKEND_VENV.exists():
        return {"ok": False, "reason": f"backend venv missing: {BACKEND_VENV}", "sha": sha}
    if not BACKEND_ENV.exists():
        return {"ok": False, "reason": f"backend .env missing: {BACKEND_ENV}", "sha": sha}

    root = Path("/home/ubuntu/salon-orchestrator/runtime/host-verifier")
    root.mkdir(parents=True, exist_ok=True)
    worktree = Path(tempfile.mkdtemp(prefix="verify-", dir=root))

    try:
        # tempfile created the dir; git worktree requires target not to exist.
        worktree.rmdir()
        fetch = subprocess.run(
            ["git", "-C", str(BACKEND_REPO), "fetch", "origin"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if fetch.returncode != 0:
            return {"ok": False, "reason": "git fetch failed", "detail": fetch.stdout[-1200:], "sha": sha}

        add = subprocess.run(
            ["git", "-C", str(BACKEND_REPO), "worktree", "add", "--detach", str(worktree), sha],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if add.returncode != 0:
            return {"ok": False, "reason": "git worktree add failed", "detail": add.stdout[-1200:], "sha": sha}

        # Settings loads PROJECT_ROOT/.env. Copy it only into this trusted verifier
        # worktree. This worktree is never exposed to Codex and is deleted afterward.
        shutil.copy2(BACKEND_ENV, worktree / ".env")
        api = worktree / "apps/api"

        tools = {
            "pytest": BACKEND_VENV / "bin/pytest",
            "ruff": BACKEND_VENV / "bin/ruff",
            "black": BACKEND_VENV / "bin/black",
        }
        missing = [name for name, path in tools.items() if not path.exists()]
        if missing:
            return {"ok": False, "reason": f"missing tools in backend venv: {', '.join(missing)}", "sha": sha}

        checks = {
            "pytest": run([str(tools["pytest"]), "-q"], api, timeout=900),
            "ruff_check": run([str(tools["ruff"]), "check", "."], api, timeout=300),
            "ruff_format": run([str(tools["ruff"]), "format", "--check", "."], api, timeout=300),
            "black": run([str(tools["black"]), "--check", "."], api, timeout=300),
        }

        ok = all(item["returncode"] == 0 for item in checks.values())
        return {
            "ok": ok,
            "sha": sha,
            "checks": checks,
            "note": "Executed in an isolated trusted host worktree pinned to the audited SHA. Secrets were not exposed to the model auditor.",
        }
    finally:
        try:
            (worktree / ".env").unlink(missing_ok=True)
        except Exception:
            pass
        subprocess.run(
            ["git", "-C", str(BACKEND_REPO), "worktree", "remove", "--force", str(worktree)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.rmtree(worktree, ignore_errors=True)


def summarize_for_model(result: dict[str, Any]) -> str:
    if not result.get("ok") and not result.get("checks"):
        return (
            "TRUSTED_HOST_VERIFIER: BLOCKED\n"
            f"SHA: {result.get('sha','')}\n"
            f"REASON: {result.get('reason','unknown')}\n"
        )

    lines = [
        "TRUSTED_HOST_VERIFIER: " + ("PASS" if result.get("ok") else "FAIL"),
        f"SHA: {result.get('sha','')}",
        "Secrets were used only by the trusted host verifier and were NOT exposed to the model auditor.",
    ]
    for name, item in (result.get("checks") or {}).items():
        status = "PASS" if item.get("returncode") == 0 else "FAIL"
        lines.append(f"{name}: {status} ({item.get('duration_seconds')}s)")
        tail = (item.get("output_tail") or "").strip().replace("\x00", "")
        if tail:
            lines.append(f"{name}_tail:\n{tail[-1500:]}")
    return "\n".join(lines) + "\n"
