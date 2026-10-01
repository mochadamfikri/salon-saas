from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

FRONTEND_REPO = Path(
    os.environ.get("CODEX_WORKSPACE", "/home/ubuntu/salon-saas-frontend")
)
NODE_BIN_DIR = Path(
    os.environ.get("FRONTEND_NODE_BIN", "/home/ubuntu/.local/node24/bin")
)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(NODE_BIN_DIR) + ":" + env.get("PATH", "")
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    return env


def _run(cmd: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=_env(),
        )
        return {
            "returncode": proc.returncode,
            "duration_seconds": round(time.monotonic() - started, 2),
            "output_tail": (proc.stdout or "")[-5000:],
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return {
            "returncode": 124,
            "duration_seconds": round(time.monotonic() - started, 2),
            "output_tail": ("TIMEOUT\n" + output)[-5000:],
        }


def verify_frontend_sha(sha: str) -> dict[str, Any]:
    node = NODE_BIN_DIR / "node"
    npm = NODE_BIN_DIR / "npm"

    if not node.exists() or not npm.exists():
        return {
            "ok": False,
            "sha": sha,
            "reason": f"Node 24 runtime missing under {NODE_BIN_DIR}",
        }

    version = _run([str(node), "-v"], FRONTEND_REPO, 30)
    node_text = (version.get("output_tail") or "").strip()
    if version["returncode"] != 0 or not node_text.startswith("v24."):
        return {
            "ok": False,
            "sha": sha,
            "reason": f"Expected Node 24, got {node_text or 'unknown'}",
        }

    root = Path(
        "/home/ubuntu/salon-orchestrator/runtime/frontend-host-verifier"
    )
    root.mkdir(parents=True, exist_ok=True)
    worktree = Path(tempfile.mkdtemp(prefix="verify-", dir=root))

    try:
        worktree.rmdir()

        subprocess.run(
            ["git", "-C", str(FRONTEND_REPO), "fetch", "origin"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=_env(),
        )

        add = subprocess.run(
            [
                "git",
                "-C",
                str(FRONTEND_REPO),
                "worktree",
                "add",
                "--detach",
                str(worktree),
                sha,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=_env(),
        )
        if add.returncode != 0:
            return {
                "ok": False,
                "sha": sha,
                "reason": "git worktree add failed",
                "detail": (add.stdout or "")[-1500:],
            }

        target_web = worktree / "apps/web"

        install = _run(
            [
                str(npm),
                "ci",
                "--prefer-offline",
                "--no-audit",
                "--no-fund",
            ],
            worktree,
            1200,
        )
        if install["returncode"] != 0:
            return {
                "ok": False,
                "sha": sha,
                "reason": "npm ci failed in isolated audit worktree",
                "install": install,
            }

        for name in (".env", ".env.local"):
            src = FRONTEND_REPO / "apps/web" / name
            if src.exists():
                shutil.copy2(src, target_web / name)

        bins = worktree / "node_modules/.bin"
        needed = ["vitest", "tsc", "eslint", "next"]
        missing = [name for name in needed if not (bins / name).exists()]
        if missing:
            return {
                "ok": False,
                "sha": sha,
                "reason": "missing frontend tools after npm ci: "
                + ", ".join(missing),
            }

        checks = {
            "vitest": _run(
                [str(npm), "--workspace", "@salon-saas/web", "run", "test"],
                worktree,
                900,
            ),
            "typescript": _run(
                [
                    str(bins / "tsc"),
                    "--noEmit",
                    "-p",
                    str(worktree / "apps/web/tsconfig.json"),
                ],
                worktree,
                600,
            ),
            "eslint": _run(
                [str(npm), "--workspace", "@salon-saas/web", "run", "lint"],
                worktree,
                600,
            ),
            "build": _run(
                [str(npm), "--workspace", "@salon-saas/web", "run", "build"],
                worktree,
                1200,
            ),
        }

        return {
            "ok": all(item["returncode"] == 0 for item in checks.values()),
            "sha": sha,
            "node_version": node_text,
            "install": {
                "returncode": install["returncode"],
                "duration_seconds": install["duration_seconds"],
            },
            "checks": checks,
            "note": (
                "Trusted host frontend verification uses an isolated worktree, "
                "fresh npm ci from the pinned lockfile, and Node 24. "
                "Environment values are not exposed to the model auditor."
            ),
        }
    finally:
        for name in (".env", ".env.local"):
            try:
                (worktree / "apps/web" / name).unlink(missing_ok=True)
            except Exception:
                pass

        subprocess.run(
            [
                "git",
                "-C",
                str(FRONTEND_REPO),
                "worktree",
                "remove",
                "--force",
                str(worktree),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=_env(),
        )
        shutil.rmtree(worktree, ignore_errors=True)


def summarize_frontend(result: dict[str, Any]) -> str:
    if not result.get("checks"):
        reason = result.get("reason", "unknown")
        install = result.get("install") or {}
        tail = (install.get("output_tail") or "").strip()

        text = (
            "TRUSTED_FRONTEND_HOST_VERIFIER: BLOCKED\n"
            f"SHA: {result.get('sha', '')}\n"
            f"REASON: {reason}\n"
        )
        if tail:
            text += f"DETAIL:\n{tail[-1600:]}\n"
        return text

    lines = [
        "TRUSTED_FRONTEND_HOST_VERIFIER: "
        + ("PASS" if result.get("ok") else "FAIL"),
        f"SHA: {result.get('sha', '')}",
        f"NODE: {result.get('node_version', '')}",
        "Dependencies installed fresh from pinned lockfile in isolated worktree.",
        "Environment values were not exposed to the model auditor.",
    ]

    for name, item in result["checks"].items():
        status = "PASS" if item["returncode"] == 0 else "FAIL"
        lines.append(
            f"{name}: {status} ({item['duration_seconds']}s)"
        )
        tail = (item.get("output_tail") or "").strip()
        if tail:
            lines.append(f"{name}_tail:\n{tail[-1600:]}")

    return "\n".join(lines) + "\n"
