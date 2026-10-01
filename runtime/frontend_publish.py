from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Any

FRONT = Path(os.environ.get("CODEX_WORKSPACE", "/home/ubuntu/salon-saas-frontend"))
NODEBIN = Path(os.environ.get("FRONTEND_NODE_BIN", "/home/ubuntu/.local/node24/bin"))
BRANCH = os.environ.get("CODEX_FRONTEND_BRANCH", "feature/phase-2-web-codex")

def env() -> dict[str, str]:
    e = os.environ.copy()
    e["PATH"] = str(NODEBIN) + ":" + e.get("PATH", "")
    e["NEXT_TELEMETRY_DISABLED"] = "1"
    e.pop("NODE_ENV", None)
    return e

def run(cmd: list[str], timeout: int = 1200) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=FRONT, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, env=env())
        return p.returncode, p.stdout or ""
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        return 124, "TIMEOUT\n" + out

def git(*args: str, check: bool = True) -> str:
    p = subprocess.run(["git","-C",str(FRONT),*args], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env())
    if check and p.returncode != 0:
        raise RuntimeError((p.stdout or "")[-1800:])
    return (p.stdout or "").strip()

def changed_paths() -> list[str]:
    # Do not use git() here: git() strips leading whitespace, while
    # porcelain status uses the first two columns as significant XY status.
    p = subprocess.run(
        ["git", "-C", str(FRONT), "status", "--porcelain=v1", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env(),
    )
    if p.returncode != 0:
        raise RuntimeError(p.stdout.decode(errors="replace")[-1800:])

    entries = p.stdout.decode(errors="surrogateescape").split("\0")
    result = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue

        path = entry[3:]

        # In -z porcelain format, rename/copy paths are separate NUL
        # records. The destination is the path in the status record.
        if len(entry) >= 2 and ("R" in entry[:2] or "C" in entry[:2]):
            if i < len(entries) and entries[i]:
                i += 1

        result.append(path)

    return result

def gate(name: str, cmd: list[str], timeout: int) -> tuple[bool, str]:
    rc, out = run(cmd, timeout)
    if rc != 0:
        return False, f"{name} gagal (exit={rc})\n{out[-2400:]}"
    return True, f"{name} PASS"

def publish_frontend_worktree(task_id: str, checkpoint: str, before_sha: str | None) -> dict[str, Any]:
    branch = git("branch","--show-current")
    if branch != BRANCH:
        return {"ok":False,"reason":f"branch salah: {branch}"}

    node = NODEBIN/"node"
    npm = NODEBIN/"npm"
    if not node.exists() or not npm.exists():
        return {"ok":False,"reason":f"Node24 tidak tersedia di {NODEBIN}"}

    head = git("rev-parse","HEAD")
    dirty = changed_paths()

    if not dirty and before_sha and head != before_sha:
        try:
            git("push","origin",branch)
        except Exception as exc:
            return {"ok":False,"reason":f"push gagal: {exc}"}
        remote = git("ls-remote","origin",f"refs/heads/{branch}").split()
        if not remote or remote[0] != head:
            return {"ok":False,"reason":"remote SHA mismatch setelah push"}
        return {"ok":True,"sha":head,"reason":"commit Codex dipush worker"}

    if not dirty:
        return {"ok":False,"reason":"Codex tidak menghasilkan perubahan frontend"}

    bad = [p for p in dirty if not (p.startswith("apps/web/") or p.startswith("docs/reports/"))]
    if bad:
        return {"ok":False,"reason":"scope violation: "+", ".join(bad[:10])}

    gates = [
        ("vitest",[str(npm),"--workspace","@salon-saas/web","run","test"],900),
        ("typescript",[str(npm),"exec","--workspace","@salon-saas/web","--","tsc","--noEmit"],600),
        ("eslint",[str(npm),"--workspace","@salon-saas/web","run","lint"],600),
        ("build",[str(npm),"--workspace","@salon-saas/web","run","build"],1200),
        ("diff-check",["git","-C",str(FRONT),"diff","--check"],120),
    ]
    evidence = []
    for name, cmd, timeout in gates:
        ok, detail = gate(name, cmd, timeout)
        evidence.append(detail)
        if not ok:
            return {"ok":False,"reason":detail,"gates":evidence}

    try:
        git("add","-A")
        git("-c","user.name=IDSE Frontend Worker",
            "-c","user.email=frontend-worker@idse.local",
            "commit","-m",f"feat(web): deliver {checkpoint} via controlled handoff")
        sha = git("rev-parse","HEAD")
        git("push","origin",branch)
    except Exception as exc:
        return {"ok":False,"reason":f"host publication gagal: {exc}","gates":evidence}

    remote = git("ls-remote","origin",f"refs/heads/{branch}").split()
    if not remote or remote[0] != sha:
        return {"ok":False,"reason":"remote SHA mismatch setelah host push"}

    if git("status","--porcelain"):
        return {"ok":False,"reason":"working tree masih kotor setelah host commit"}

    return {"ok":True,"sha":sha,"reason":"host gates PASS; worker commit+push selesai","gates":evidence}
