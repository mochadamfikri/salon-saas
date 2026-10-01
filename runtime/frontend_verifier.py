from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

FRONTEND_REPO = Path(os.environ.get("CODEX_WORKSPACE", "/home/ubuntu/salon-saas-frontend"))


def _run(cmd: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        cmd, cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout, env=os.environ.copy(),
    )
    return {
        "returncode": proc.returncode,
        "duration_seconds": round(time.monotonic() - started, 2),
        "output_tail": (proc.stdout or "")[-3500:],
    }


def verify_frontend_sha(sha: str) -> dict[str, Any]:
    root = Path("/home/ubuntu/salon-orchestrator/runtime/frontend-host-verifier")
    root.mkdir(parents=True, exist_ok=True)
    worktree = Path(tempfile.mkdtemp(prefix="verify-", dir=root))
    try:
        worktree.rmdir()
        subprocess.run(
            ["git", "-C", str(FRONTEND_REPO), "fetch", "origin"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        add = subprocess.run(
            ["git", "-C", str(FRONTEND_REPO), "worktree", "add", "--detach", str(worktree), sha],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        if add.returncode != 0:
            return {"ok": False, "sha": sha, "reason": "git worktree add failed", "detail": add.stdout[-1000:]}

        source_web = FRONTEND_REPO / "apps/web"
        target_web = worktree / "apps/web"
        source_nm = source_web / "node_modules"
        if not source_nm.exists():
            return {"ok": False, "sha": sha, "reason": f"frontend node_modules missing: {source_nm}"}

        (target_web / "node_modules").symlink_to(source_nm, target_is_directory=True)

        for name in (".env", ".env.local"):
            src = source_web / name
            if src.exists():
                shutil.copy2(src, target_web / name)

        bins = target_web / "node_modules/.bin"
        needed = ["vitest", "tsc", "eslint", "next"]
        missing = [x for x in needed if not (bins / x).exists()]
        if missing:
            return {"ok": False, "sha": sha, "reason": "missing frontend tools: " + ", ".join(missing)}

        checks = {
            "vitest": _run([str(bins / "vitest"), "run"], target_web, 900),
            "typescript": _run([str(bins / "tsc"), "--noEmit"], target_web, 600),
            "eslint": _run([str(bins / "eslint"), "."], target_web, 600),
            "build": _run([str(bins / "next"), "build"], target_web, 1200),
        }
        return {
            "ok": all(v["returncode"] == 0 for v in checks.values()),
            "sha": sha,
            "checks": checks,
            "note": "Trusted host frontend verification pinned to audited SHA. Environment values were not exposed to the model auditor.",
        }
    finally:
        for name in (".env", ".env.local"):
            try:
                (worktree / "apps/web" / name).unlink(missing_ok=True)
            except Exception:
                pass
        try:
            nm = worktree / "apps/web/node_modules"
            if nm.is_symlink():
                nm.unlink()
        except Exception:
            pass
        subprocess.run(
            ["git", "-C", str(FRONTEND_REPO), "worktree", "remove", "--force", str(worktree)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        shutil.rmtree(worktree, ignore_errors=True)


def summarize_frontend(result: dict[str, Any]) -> str:
    if not result.get("checks"):
        return (
            "TRUSTED_FRONTEND_HOST_VERIFIER: BLOCKED\n"
            f"SHA: {result.get('sha','')}\n"
            f"REASON: {result.get('reason','unknown')}\n"
        )
    lines = [
        "TRUSTED_FRONTEND_HOST_VERIFIER: " + ("PASS" if result.get("ok") else "FAIL"),
        f"SHA: {result.get('sha','')}",
        "Environment values were not exposed to the model auditor.",
    ]
    for name, item in result["checks"].items():
        status = "PASS" if item["returncode"] == 0 else "FAIL"
        lines.append(f"{name}: {status} ({item['duration_seconds']}s)")
        tail = (item.get("output_tail") or "").strip()
        if tail:
            lines.append(f"{name}_tail:\n{tail[-1200:]}")
    return "\n".join(lines) + "\n"
