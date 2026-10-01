from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import secrets
import shutil
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timezone
import re
from pathlib import Path

import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from common import (
    BACKEND_WORKSPACE,
    FRONTEND_WORKSPACE,
    ROOT,
    db,
    emit,
    git_info,
    init_db,
    now_iso,
)

app = FastAPI(title="Salon SaaS Orchestrator")
SESSION_SECRET = os.environ.get("SALON_ADMIN_SESSION_SECRET", "change-me")
ADMIN_USER = os.environ.get("SALON_ADMIN_USER", "owner")
ADMIN_PASSWORD = os.environ.get("SALON_ADMIN_PASSWORD", "change-me")
COOKIE = "salon_ops_session"


@app.on_event("startup")
def startup() -> None:
    init_db()


def sign(value: str) -> str:
    return hmac.new(SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def make_session() -> str:
    payload = f"{int(time.time())}:{secrets.token_hex(16)}"
    return payload + ":" + sign(payload)


def valid_session(value: str | None) -> bool:
    if not value:
        return False
    try:
        payload, signature = value.rsplit(":", 1)
        timestamp = int(payload.split(":", 1)[0])
        return hmac.compare_digest(signature, sign(payload)) and time.time() - timestamp < 7 * 86400
    except Exception:
        return False


def require(request: Request) -> str:
    session = request.cookies.get(COOKIE)
    if not valid_session(session):
        raise HTTPException(401, "login required")
    return session or ""


def csrf_for(session: str) -> str:
    return hmac.new(SESSION_SECRET.encode(), ("csrf:" + session).encode(), hashlib.sha256).hexdigest()


def require_csrf(request: Request) -> None:
    session = require(request)
    provided = request.headers.get("x-csrf-token", "")
    if not hmac.compare_digest(provided, csrf_for(session)):
        raise HTTPException(403, "invalid csrf token")


def query_all(sql: str, args=()):
    con = db()
    result = [dict(row) for row in con.execute(sql, args).fetchall()]
    con.close()
    return result


def query_one(sql: str, args=()):
    con = db()
    row = con.execute(sql, args).fetchone()
    con.close()
    return dict(row) if row else None


STATUS_ID = {
    "QUEUED": ("🕒", "Antrean", "Menunggu giliran worker."),
    "RUNNING": ("🔵", "Sedang dikerjakan", "Worker sedang mengerjakan task."),
    "READY_FOR_AUDIT": ("🟣", "Siap diaudit", "Implementasi selesai dan menunggu pemeriksaan auditor."),
    "WAITING_DEPENDENCY": ("🔒", "Menunggu dependensi", "Belum boleh berjalan karena checkpoint sebelumnya belum Lulus Final."),
    "PASS_CANDIDATE": ("🟡", "Kandidat lulus", "Auto Auditor lulus; masih menunggu final review."),
    "FINAL_PASS": ("✅", "Lulus final", "Checkpoint telah disetujui final dan dependensi berikutnya boleh terbuka."),
    "REVISE_REQUIRED": ("🔁", "Perlu revisi", "Auditor menemukan masalah; task perbaikan harus dikerjakan dan diaudit ulang."),
    "REVISE": ("🔁", "Sedang revisi", "Task dikembalikan ke engineer untuk diperbaiki."),
    "COMPLETED": ("✅", "Selesai", "Task implementasi/revisi selesai dan checkpoint terkait telah lulus."),
    "BLOCKED": ("⛔", "Terblokir", "Tidak dapat dilanjutkan sampai penyebab blokir diselesaikan."),
    "ERROR": ("🚨", "Error", "Terjadi kegagalan operasional yang perlu diperiksa."),
    "WAITING": ("⏸️", "Menunggu", "Worker hidup tetapi belum memiliki task yang eligible."),
    "AUDITING": ("🔍", "Sedang audit", "Auditor sedang memeriksa source, test, dan evidence."),
    "WAITING_REVISION": ("🔁", "Menunggu revisi", "Auditor menunggu hasil perbaikan engineer."),
    "PAUSED": ("⏸️", "Dijeda", "Worker dihentikan sementara oleh Owner."),
    "OFFLINE": ("⚫", "Offline", "Service worker tidak aktif."),
    "RECOVERING": ("🛠️", "Pemulihan", "Worker mencoba pulih dan mengulang task secara otomatis."),
    "CANCELLED": ("🚫", "Dibatalkan", "Task dibatalkan sebelum mulai."),
    "PENDING": ("⚪", "Belum dimulai", "Checkpoint belum dibuka."),
    "ACTIVE": ("🚀", "Aktif", "Phase sedang aktif."),
    "VALIDATED": ("📦", "Tervalidasi", "Phase sudah valid dan menunggu dependency/approval."),
}


def status_id(state: str | None) -> dict:
    raw = str(state or "PENDING")
    icon, label, detail = STATUS_ID.get(raw, ("ℹ️", raw, "Status sistem."))
    return {"raw": raw, "icon": icon, "label": label, "detail": detail}


def _phase2_checkpoint_stats():
    try:
        rows = query_all(
            "SELECT checkpoint,backend_state,frontend_state,frontend_task_id,frontend_audit_task_id "
            "FROM workflow_checkpoints WHERE phase=2 ORDER BY checkpoint"
        )
    except Exception:
        rows = []

    by_cp = {r["checkpoint"]: r for r in rows}
    backend = [
        {"checkpoint": "P2-A", "state": "FINAL_PASS"},
        {"checkpoint": "P2-B", "state": "FINAL_PASS"},
        {"checkpoint": "P2-C", "state": (by_cp.get("P2-C") or {}).get("backend_state", "FINAL_PASS")},
        {"checkpoint": "P2-D", "state": (by_cp.get("P2-D") or {}).get("backend_state", "PENDING")},
        {"checkpoint": "P2-E", "state": (by_cp.get("P2-E") or {}).get("backend_state", "PENDING")},
    ]
    frontend = [
        {"checkpoint": "P2-B", "state": "FINAL_PASS"},
        {"checkpoint": "P2-C", "state": (by_cp.get("P2-C") or {}).get("frontend_state", "PENDING")},
        {"checkpoint": "P2-D", "state": (by_cp.get("P2-D") or {}).get("frontend_state", "PENDING")},
        {"checkpoint": "P2-E", "state": (by_cp.get("P2-E") or {}).get("frontend_state", "PENDING")},
    ]
    for item in backend + frontend:
        item["status"] = status_id(item["state"])
    return backend, frontend


def _pct(items):
    if not items:
        return 0
    return round(sum(1 for x in items if x["state"] == "FINAL_PASS") * 100 / len(items))


def _worker_reason(row: dict) -> str:
    status = row.get("status")
    wid = row.get("id")
    activity = row.get("current_activity")
    if status in ("RUNNING", "AUDITING", "RECOVERING", "ERROR", "BLOCKED") and activity:
        return str(activity)
    if wid == "notifier":
        if status == "WAITING":
            return "Telegram belum dikonfigurasi; notifier menunggu token bot dan chat ID."
        if status == "RUNNING":
            return activity or "Notifier Telegram aktif dan menunggu event penting."
    if status == "WAITING":
        if wid == "hermes":
            return "Tidak ada task backend yang eligible; menunggu dependency atau phase berikutnya."
        if wid == "codex":
            return "Tidak ada task frontend yang eligible; menunggu backend dan frontend sebelumnya Lulus Final."
        if wid == "auditor":
            return "Tidak ada task audit yang siap diperiksa."
    return activity or "Status worker aktif."


@app.get("/api/project/stats")
def project_stats(request: Request):
    require(request)
    config = yaml.safe_load((ROOT / "phase.yaml").read_text()) or {}
    current_phase = int(config.get("current_phase", 2))
    backend, frontend = _phase2_checkpoint_stats()

    audit_rows = query_all(
        "SELECT state,COUNT(*) AS total FROM tasks WHERE target_agent='auditor' GROUP BY state ORDER BY state"
    )
    audit_counts = {r["state"]: r["total"] for r in audit_rows}

    workers = []
    for row in query_all("SELECT * FROM workers ORDER BY id"):
        row["status_display"] = status_id(row.get("status"))
        row["reason"] = _worker_reason(row)
        workers.append(row)

    uploads = query_all(
        "SELECT id,phase,status,master_spec_name,created_at,activated_at FROM phase_uploads ORDER BY phase,created_at"
    )
    phase_pipeline = [
        {"phase": 1, "state": "FINAL_PASS", "label": "Selesai"},
        {"phase": 2, "state": "ACTIVE" if current_phase == 2 else "FINAL_PASS", "label": "Aktif" if current_phase == 2 else "Selesai"},
    ]
    seen = {1, 2}
    for u in uploads:
        ph = int(u["phase"])
        if ph in seen:
            continue
        seen.add(ph)
        raw = u["status"]
        state = "WAITING_DEPENDENCY" if raw == "VALIDATED" and ph > current_phase else raw
        phase_pipeline.append({"phase": ph, "state": state, "label": status_id(state)["label"]})
    phase_pipeline.sort(key=lambda x: x["phase"])

    bp = _pct(backend)
    fp = _pct(frontend)
    overall = round((bp + fp) / 2)
    next_frontend = next((x for x in frontend if x["state"] != "FINAL_PASS"), None)
    next_action = (
        f"Frontend {next_frontend['checkpoint']}: {next_frontend['status']['label']}"
        if next_frontend
        else "Semua checkpoint frontend Phase 2 Lulus Final; lanjut integration closure."
    )

    return {
        "current_phase": current_phase,
        "phase_status": config.get("phase_status", "active"),
        "overall_percent": overall,
        "backend_percent": bp,
        "frontend_percent": fp,
        "backend": backend,
        "frontend": frontend,
        "audit_counts": audit_counts,
        "workers": workers,
        "phase_pipeline": phase_pipeline,
        "next_action": next_action,
        "status_legend": [
            {"state": k, **status_id(k)}
            for k in (
                "QUEUED","RUNNING","READY_FOR_AUDIT","WAITING_DEPENDENCY",
                "PASS_CANDIDATE","FINAL_PASS","REVISE_REQUIRED","REVISE",
                "COMPLETED","BLOCKED","ERROR","PAUSED","CANCELLED"
            )
        ],
    }


@app.get("/api/telegram-status")
def telegram_status(request: Request):
    require(request)
    notifier = query_one("SELECT * FROM workers WHERE id='notifier'") or {}
    pending = query_one(
        "SELECT COUNT(*) AS total FROM events WHERE telegram_sent_at IS NULL "
        "AND severity IN ('SUCCESS','WARNING','CRITICAL','OWNER_ACTION_REQUIRED')"
    ) or {"total": 0}
    configured = notifier.get("status") not in (None, "OFFLINE", "WAITING")
    return {
        "configured": configured,
        "status": notifier.get("status", "OFFLINE"),
        "status_display": status_id(notifier.get("status", "OFFLINE")),
        "pending_important_events": int(pending["total"]),
        "last_log": notifier.get("last_log"),
        "heartbeat": notifier.get("last_heartbeat"),
    }


@app.post("/api/telegram-test")
def telegram_test(request: Request):
    require_csrf(request)
    notifier = query_one("SELECT * FROM workers WHERE id='notifier'") or {}
    if notifier.get("status") in (None, "OFFLINE", "WAITING"):
        raise HTTPException(
            409,
            "Telegram notifier belum dikonfigurasi. Isi TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID pada environment service.",
        )
    emit(
        "orchestrator",
        "telegram.test",
        "SUCCESS",
        "Tes notifikasi Telegram",
        "Notifikasi test dari IDSE Network Developing Panel.",
        phase=int((yaml.safe_load((ROOT / "phase.yaml").read_text()) or {}).get("current_phase", 2)),
    )
    return {"ok": True, "message": "Event tes dibuat. Notifier akan mengirimkannya otomatis."}


@app.get("/login", response_class=HTMLResponse)
def login_page() -> str:
    return """<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>
    <style>body{font-family:system-ui;background:#0b0d10;color:#eee;display:grid;place-items:center;height:100vh;margin:0}form{background:#171a20;padding:28px;border-radius:18px;width:min(360px,85vw)}input,button{width:100%;padding:12px;margin:7px 0;border-radius:10px;border:1px solid #333;background:#0f1115;color:#fff;box-sizing:border-box}button{background:#fff;color:#111;font-weight:700}</style>
    <form method=post><h2>IDSE NETWORK DEVELOPING PANEL</h2><input name=username placeholder=User autocomplete=username><input type=password name=password placeholder=Password autocomplete=current-password><button>Login</button></form>"""


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if not (
        hmac.compare_digest(username, ADMIN_USER)
        and hmac.compare_digest(password, ADMIN_PASSWORD)
    ):
        raise HTTPException(401, "invalid login")
    session = make_session()
    response = RedirectResponse("/", 303)
    response.set_cookie(
        COOKIE,
        session,
        httponly=True,
        samesite="strict",
        secure=os.environ.get("SALON_COOKIE_SECURE", "false").lower() == "true",
        max_age=7 * 86400,
    )
    return response


@app.post("/logout")
def logout():
    response = RedirectResponse("/login", 303)
    response.delete_cookie(COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    session = request.cookies.get(COOKIE)
    if not valid_session(session):
        return RedirectResponse("/login")
    return HTMLResponse(DASHBOARD.replace("__CSRF__", csrf_for(session or "")))


@app.get("/api/health")
def health():
    return {"ok": True, "time": now_iso()}


@app.get("/api/project")
def project(request: Request):
    require(request)
    config = yaml.safe_load((ROOT / "phase.yaml").read_text()) or {}
    config["backend_git"] = git_info(BACKEND_WORKSPACE)
    config["frontend_git"] = git_info(FRONTEND_WORKSPACE)
    return config


@app.get("/api/workers")
def workers(request: Request):
    require(request)
    return query_all("SELECT * FROM workers ORDER BY id")



@app.get("/api/workers/{worker_id}/detail")
def worker_detail(request: Request, worker_id: str):
    require(request)
    worker = query_one("SELECT * FROM workers WHERE id=?", (worker_id,))
    if not worker:
        raise HTTPException(404, "worker not found")

    task = None
    if worker.get("current_task_id"):
        task = query_one("SELECT * FROM tasks WHERE id=?", (worker["current_task_id"],))

    events = query_all(
        "SELECT timestamp,severity,title,message,type,task_id "
        "FROM events "
        "WHERE source=? OR (? IS NOT NULL AND task_id=?) "
        "ORDER BY timestamp DESC LIMIT 12",
        (worker_id, worker.get("current_task_id"), worker.get("current_task_id")),
    )

    progress = int(worker.get("progress_pct") or 0)
    if worker.get("status") in ("READY_FOR_AUDIT",):
        progress = 100
    elif worker.get("status") in ("WAITING", "OFFLINE", "PAUSED") and not worker.get("current_task_id"):
        progress = 0

    return {
        "worker": worker,
        "task": task,
        "events": events,
        "progress_pct": max(0, min(progress, 100)),
        "progress_is_estimate": True,
    }


@app.get("/api/workers/{worker_id}/logs")
def worker_logs(request: Request, worker_id: str, limit: int = 200):
    require(request)
    path = ROOT / "runtime/logs" / f"{worker_id}.log"
    lines = path.read_text(errors="replace").splitlines()[-min(limit, 2000) :] if path.exists() else []
    return {"lines": lines}


@app.post("/api/workers/{worker_id}/pause")
def pause_worker(request: Request, worker_id: str):
    require_csrf(request)
    if worker_id not in ("hermes", "codex"):
        raise HTTPException(400, "worker cannot be paused here")
    con = db()
    con.execute("UPDATE workers SET paused=1,status='PAUSED' WHERE id=?", (worker_id,))
    con.commit()
    con.close()
    emit("orchestrator", "worker.paused", "WARNING", f"{worker_id.title()} paused", "Queue consumption paused by Owner")
    return {"ok": True}


@app.post("/api/workers/{worker_id}/resume")
def resume_worker(request: Request, worker_id: str):
    require_csrf(request)
    if worker_id not in ("hermes", "codex"):
        raise HTTPException(400, "worker cannot be resumed here")
    con = db()
    con.execute("UPDATE workers SET paused=0,status='WAITING' WHERE id=?", (worker_id,))
    con.commit()
    con.close()
    emit("orchestrator", "worker.resumed", "INFO", f"{worker_id.title()} resumed", "Queue consumption resumed by Owner")
    return {"ok": True}


@app.post("/api/workers/{worker_id}/retry")
def retry_worker(request: Request, worker_id: str):
    require_csrf(request)
    con = db()
    row = con.execute("SELECT current_task_id FROM workers WHERE id=?", (worker_id,)).fetchone()
    if not row or not row[0]:
        con.close()
        raise HTTPException(409, "no current task")
    task_id = row[0]
    con.execute("UPDATE tasks SET state='QUEUED',last_error=NULL WHERE id=?", (task_id,))
    con.execute("UPDATE workers SET status='WAITING',paused=0 WHERE id=?", (worker_id,))
    con.commit()
    con.close()
    emit("orchestrator", "task.queued", "WARNING", "Task manually retried", task_id, task_id=task_id)
    return {"ok": True}


@app.get("/api/tasks")
def tasks(request: Request):
    require(request)
    return query_all("SELECT * FROM tasks ORDER BY created_at DESC")


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(request: Request, task_id: str):
    require_csrf(request)
    con = db()
    row = con.execute("SELECT state FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "task not found")
    if row[0] not in ("QUEUED", "WAITING_DEPENDENCY"):
        con.close()
        raise HTTPException(409, "task already started")
    con.execute("UPDATE tasks SET state='CANCELLED',finished_at=? WHERE id=?", (now_iso(), task_id))
    con.commit()
    con.close()
    emit("orchestrator", "task.cancelled", "WARNING", "Task cancelled", task_id, task_id=task_id)
    return {"ok": True}


@app.get("/api/notifications")
def notifications(request: Request):
    require(request)
    return query_all("SELECT * FROM events ORDER BY timestamp DESC LIMIT 300")


@app.post("/api/notifications/read-all")
def read_all(request: Request):
    require_csrf(request)
    con = db()
    con.execute("UPDATE events SET read_at=COALESCE(read_at,?)", (now_iso(),))
    con.commit()
    con.close()
    return {"ok": True}


def _report_roots():
    return [
        ("backend", BACKEND_WORKSPACE / "docs/reports", BACKEND_WORKSPACE),
        ("frontend", FRONTEND_WORKSPACE / "docs/reports", FRONTEND_WORKSPACE),
        ("orchestrator", ROOT / "audit", ROOT),
    ]


def _report_created_at(path: Path, agent: str, repo: Path, content: str) -> str:
    for pattern in (
        r"(?mi)^\s*-\s*Generated:\s*(.+?)\s*$",
        r"(?mi)^\s*Generated:\s*(.+?)\s*$",
        r"(?mi)^\s*Created:\s*(.+?)\s*$",
        r"(?mi)^\s*Completed:\s*(.+?)\s*$",
    ):
        m = re.search(pattern, content)
        if m:
            return m.group(1).strip()

    try:
        rel = path.relative_to(repo)
        proc = subprocess.run(
            ["git", "-C", str(repo), "log", "--follow", "--diff-filter=A", "--format=%cI", "--", str(rel)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        line = next((x.strip() for x in proc.stdout.splitlines() if x.strip()), "")
        if line:
            return line
    except Exception:
        pass

    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def _report_status(path: Path, content: str) -> str:
    task = query_one("SELECT state FROM tasks WHERE result_path=?", (str(path),))
    if task and task.get("state"):
        return str(task["state"])

    for pattern in (
        r"(?mi)^\s*[-*]?\s*(?:P\d+-[A-Z]\s+)?Status\s*:\s*(.+?)\s*$",
        r"(?mi)^\s*AUDIT_VERDICT\s*:\s*(.+?)\s*$",
    ):
        m = re.search(pattern, content)
        if m:
            return m.group(1).strip()[:100]

    upper = content.upper()
    for token in ("FINAL PASS", "READY FOR AUDIT", "PASS_CANDIDATE", "REVISE_REQUIRED", "BLOCKED", "COMPLETE"):
        if token in upper:
            return token
    return "REPORT"


def report_index():
    result = []
    now = now_iso()
    con = db()

    for agent, base, repo in _report_roots():
        if not base.exists():
            continue
        for path in base.rglob("*.md"):
            report_id = hashlib.sha1(str(path).encode()).hexdigest()[:16]
            existing = con.execute(
                "SELECT first_seen_at FROM report_registry WHERE id=?",
                (report_id,),
            ).fetchone()
            if not existing:
                con.execute(
                    "INSERT INTO report_registry(id,agent,name,path,first_seen_at,last_seen_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (report_id, agent, path.name, str(path), now, now),
                )
                first_seen = now
            else:
                first_seen = existing["first_seen_at"]
                con.execute(
                    "UPDATE report_registry SET agent=?,name=?,path=?,last_seen_at=? WHERE id=?",
                    (agent, path.name, str(path), now, report_id),
                )

            result.append(
                {
                    "id": report_id,
                    "agent": agent,
                    "name": path.name,
                    "path": str(path),
                    "mtime": path.stat().st_mtime,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                    "first_seen_at": first_seen,
                    "size_bytes": path.stat().st_size,
                }
            )

    con.commit()
    con.close()
    return sorted(result, key=lambda x: x["mtime"], reverse=True)


@app.get("/api/reports")
def reports(request: Request):
    require(request)
    return report_index()



@app.get("/api/reports/{report_id}")
def report_detail(request: Request, report_id: str):
    require(request)
    for item in report_index():
        if item["id"] != report_id:
            continue

        path = Path(item["path"])
        content = path.read_text(encoding="utf-8", errors="replace")
        repo = {
            "backend": BACKEND_WORKSPACE,
            "frontend": FRONTEND_WORKSPACE,
            "orchestrator": ROOT,
        }[item["agent"]]

        return {
            **item,
            "created_at": _report_created_at(path, item["agent"], repo, content),
            "status": _report_status(path, content),
            "content": content[:250000],
            "truncated": len(content) > 250000,
            "download_url": f"/api/reports/{report_id}/download",
        }

    raise HTTPException(404, "report not found")


@app.get("/api/reports/{report_id}/download")
def report_download(request: Request, report_id: str):
    require(request)
    for item in report_index():
        if item["id"] == report_id:
            return FileResponse(item["path"], filename=item["name"])
    raise HTTPException(404, "report not found")


@app.get("/api/phases")
def phases(request: Request):
    require(request)
    return query_all("SELECT * FROM phase_uploads ORDER BY created_at DESC")


def validate_zip(archive: zipfile.ZipFile) -> None:
    for info in archive.infolist():
        parts = Path(info.filename).parts
        file_type = (info.external_attr >> 16) & 0o170000
        if info.filename.startswith("/") or ".." in parts or file_type == 0o120000:
            raise HTTPException(400, "unsafe zip path")
        if info.file_size > 2_000_000:
            raise HTTPException(400, "phase package member too large")


@app.post("/api/phases/upload")
async def phase_upload(request: Request, file: UploadFile = File(...)):
    require_csrf(request)
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "upload too large")
    upload_id = "phase_" + uuid.uuid4().hex[:12]
    folder = ROOT / "runtime/uploads" / upload_id
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {}
    try:
        if file.filename and file.filename.endswith(".md"):
            if not file.filename.startswith("PHASE") or not file.filename.endswith("_MASTER_SPEC.md"):
                raise HTTPException(400, "expected PHASE<N>_MASTER_SPEC.md")
            (folder / file.filename).write_bytes(data)
        elif file.filename and file.filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                validate_zip(archive)
                archive.extractall(folder)
        else:
            raise HTTPException(400, "only .md or .zip allowed")

        specs = list(folder.rglob("PHASE*_MASTER_SPEC.md"))
        if len(specs) != 1:
            raise HTTPException(400, "package must contain exactly one PHASE<N>_MASTER_SPEC.md")
        spec = specs[0]
        import re

        match = re.search(r"PHASE(\d+)_", spec.name)
        if not match:
            raise HTTPException(400, "invalid phase filename")
        phase = int(match.group(1))
        manifests = list(folder.rglob("PHASE*_TASKS.yaml"))
        if manifests:
            manifest = yaml.safe_load(manifests[0].read_text()) or {}

        con = db()
        con.execute(
            """INSERT INTO phase_uploads
            (id,phase,status,upload_path,master_spec_name,manifest_json,created_at)
            VALUES(?,?,?,?,?,?,?)""",
            (
                upload_id,
                phase,
                "VALIDATED",
                str(folder),
                spec.name,
                json.dumps(manifest),
                now_iso(),
            ),
        )
        con.commit()
        con.close()
        emit("orchestrator", "phase.ready_to_activate", "SUCCESS", f"Phase {phase} validated", spec.name, phase=phase)
        return {"id": upload_id, "phase": phase, "status": "VALIDATED", "master_spec": spec.name, "manifest": manifest}
    except Exception:
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
        raise


@app.post("/api/phases/{upload_id}/activate")
def phase_activate(request: Request, upload_id: str):
    require_csrf(request)
    upload = query_one("SELECT * FROM phase_uploads WHERE id=?", (upload_id,))
    if not upload or upload["status"] != "VALIDATED":
        raise HTTPException(409, "phase is not validated")

    phase = int(upload["phase"])
    folder = Path(upload["upload_path"])
    specs = list(folder.rglob(upload["master_spec_name"]))
    if len(specs) != 1:
        raise HTTPException(409, "phase spec missing")
    spec = specs[0]
    target = ROOT / "knowledge/phases" / spec.name
    shutil.copy2(spec, target)

    config = yaml.safe_load((ROOT / "phase.yaml").read_text()) or {}
    config["current_phase"] = phase
    config["phase_status"] = "active"
    (ROOT / "phase.yaml").write_text(yaml.safe_dump(config, sort_keys=False))

    manifest = json.loads(upload["manifest_json"] or "{}")
    if isinstance(manifest, dict):
        for task in manifest.get("tasks", []):
            agent = str(task.get("target_agent", "")).lower()
            if agent not in ("hermes", "codex"):
                continue
            task_id = str(task.get("id") or f"P{phase}-{task.get('checkpoint', 'TASK')}")
            body = task.get("body") or (
                f"TARGET_AGENT: {agent.upper()}\n"
                f"TASK_ID: {task_id}\n"
                f"PHASE: {phase}\n"
                f"CHECKPOINT: {task.get('checkpoint', '')}\n"
                "STATUS: QUEUED\n\n"
                f"{task.get('instruction', '')}\n"
            )
            task_path = ROOT / "inbox" / agent / f"{task_id}.md"
            task_path.write_text(body, encoding="utf-8")

    try:
        subprocess.run(
            ["git", "-C", str(ROOT), "add", "knowledge/phases", "phase.yaml", "inbox"],
            check=True,
        )
        commit = subprocess.run(
            ["git", "-C", str(ROOT), "commit", "-m", f"orchestrator: activate Phase {phase}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if commit.returncode not in (0, 1):
            raise subprocess.CalledProcessError(commit.returncode, commit.args, output=commit.stdout)
        subprocess.run(["git", "-C", str(ROOT), "push", "origin", "orchestration"], check=True)
    except subprocess.CalledProcessError as exc:
        emit("orchestrator", "git.push_failed", "CRITICAL", "Orchestration git sync failed", str(exc), phase=phase)
        raise HTTPException(500, "git commit/push failed") from exc

    con = db()
    con.execute(
        "UPDATE phase_uploads SET status='ACTIVATED',activated_at=? WHERE id=?",
        (now_iso(), upload_id),
    )
    con.commit()
    con.close()
    emit("orchestrator", "phase.activated", "SUCCESS", f"Phase {phase} activated", spec.name, phase=phase)
    return {"ok": True, "phase": phase}


DASHBOARD = r"""<!doctype html>
<html><head><meta name=viewport content="width=device-width,initial-scale=1"><title>Developing Panel</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0a0c10;color:#f4f4f5;font-family:system-ui,-apple-system,sans-serif}.top{position:sticky;top:0;background:#11141aee;backdrop-filter:none;padding:14px 18px;border-bottom:1px solid #242833;display:flex;justify-content:space-between;z-index:5}.wrap{max-width:1100px;margin:auto;padding:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.card{background:#141821;border:1px solid #262c38;border-radius:16px;padding:16px}.pill{display:inline-block;padding:4px 9px;border-radius:99px;background:#252b37;font-size:12px}.good{background:#143322}.bad{background:#3a1717}.warn{background:#3a3012}button,input{border:1px solid #303746;background:#181d26;color:#fff;border-radius:10px;padding:9px 12px}button{cursor:pointer}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:10px;border-bottom:1px solid #272d38;text-align:left}.section{margin-top:24px}.muted{color:#9ca3af;font-size:13px}.hidden{display:none}@media(max-width:640px){.wrap{padding:12px}td:nth-child(n+4),th:nth-child(n+4){display:none}}
</style><style>
/* IDSE_PANEL_V1 */
:root{--bg:#070a10;--card:#121722;--line:#273041;--accent:#7c8cff;--cyan:#4fd8ff;--muted:#94a3b8;--ok:#36d98b;--warn:#f4c451;--bad:#ff6475}
body{background:radial-gradient(circle at 15% -5%,rgba(124,140,255,.16),transparent 32%),radial-gradient(circle at 90% 8%,rgba(79,216,255,.10),transparent 28%),var(--bg);background-attachment:scroll}
.top{min-height:76px;background:rgba(8,11,17,.88);border-bottom:1px solid rgba(148,163,184,.15);box-shadow:0 12px 36px rgba(0,0,0,.22)}
.top>b{display:flex;align-items:center;gap:10px;letter-spacing:.025em}
.top>b:before{content:"ID";width:38px;height:38px;display:grid;place-items:center;border-radius:12px;background:linear-gradient(135deg,var(--accent),var(--cyan));font-size:12px;box-shadow:0 0 24px rgba(124,140,255,.3)}
.wrap>div:first-child{display:flex;gap:7px;flex-wrap:wrap;padding:6px;border:1px solid rgba(148,163,184,.13);border-radius:14px;background:rgba(16,21,30,.62);backdrop-filter:none;width:max-content;max-width:100%}
.wrap>div:first-child button{background:transparent;border-color:transparent;font-weight:650;transition:.18s ease}
.wrap>div:first-child button:hover{background:rgba(124,140,255,.14);border-color:rgba(124,140,255,.25);transform:translateY(-1px)}
.card{background:linear-gradient(145deg,rgba(22,28,40,.92),rgba(13,17,25,.9));border-color:rgba(148,163,184,.16);border-radius:20px;box-shadow:0 16px 45px rgba(0,0,0,.16);transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease}
.card:hover{transform:translateY(-2px);border-color:rgba(124,140,255,.32);box-shadow:0 20px 55px rgba(0,0,0,.24)}
.pill{position:relative;padding-left:21px;font-weight:700}
.pill:before{content:"";position:absolute;left:8px;top:50%;width:7px;height:7px;border-radius:50%;transform:translateY(-50%);background:#8993a4}
.pill.good{background:rgba(29,112,69,.30);color:#c2f8dc}.pill.good:before{background:var(--ok);box-shadow:0 0 9px rgba(54,217,139,.75);animation:pulse 2s infinite}
.pill.warn{background:rgba(126,95,20,.28);color:#ffe2a0}.pill.warn:before{background:var(--warn)}
.pill.bad{background:rgba(139,35,51,.28);color:#ffc1c8}.pill.bad:before{background:var(--bad)}
button{transition:transform .15s ease,background .15s ease,border-color .15s ease}button:active{transform:scale(.97)}
.section:not(.hidden){animation:fadeUp .23s ease both}
h2{letter-spacing:-.035em}
.muted{color:var(--muted)}
tbody tr{transition:background .18s ease}tbody tr:hover{background:rgba(124,140,255,.05)}
#notifs .card{border-left:3px solid rgba(124,140,255,.55)}
@keyframes pulse{50%{opacity:.55;transform:translateY(-50%) scale(.82)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media(max-width:640px){.top>b{font-size:12px}.top>b:before{width:34px;height:34px}.wrap>div:first-child{width:100%;overflow-x:auto;flex-wrap:nowrap}.wrap>div:first-child button{flex:0 0 auto}}


/* IDSE_MOBILE_PERFORMANCE_V1 */

@media (pointer:coarse){

  body{
    background:
      radial-gradient(circle at 15% 0%,rgba(124,140,255,.10),transparent 30%),
      #070a10 !important;
    background-attachment:scroll !important;
  }

  .top,
  .wrap>div:first-child{
    backdrop-filter:none !important;
    -webkit-backdrop-filter:none !important;
  }

  .card{
    box-shadow:0 5px 18px rgba(0,0,0,.13) !important;
    transition:none !important;
    transform:none !important;
  }

  .card:hover{
    transform:none !important;
    box-shadow:0 5px 18px rgba(0,0,0,.13) !important;
  }

  button{
    transition:none !important;
  }

  .section:not(.hidden){
    animation:none !important;
  }

  .pill.good:before{
    animation:none !important;
    box-shadow:0 0 5px rgba(54,217,139,.45) !important;
  }

  #notifs .card{
    content-visibility:auto;
    contain-intrinsic-size:130px;
  }

  #workers .card{
    content-visibility:auto;
    contain-intrinsic-size:210px;
  }
}

/* Hover animation hanya untuk device yang benar-benar punya mouse */
@media (hover:hover) and (pointer:fine){
  .card:hover{
    transform:translateY(-2px);
  }
}


/* IDSE_LIGHTWEIGHT_V2 */

body{
  background:#080b11 !important;
  background-image:none !important;
}

.top{
  position:relative !important;
  min-height:70px !important;
  display:flex !important;
  align-items:center !important;
  justify-content:space-between !important;
  gap:12px !important;
  padding:13px 18px !important;
  background:#0c1017 !important;
  box-shadow:none !important;
}

.brandbar{
  display:flex;
  align-items:center;
  gap:11px;
  min-width:0;
}

.brandicon{
  width:40px;
  height:40px;
  flex:0 0 40px;
  display:grid;
  place-items:center;
  border-radius:12px;
  font-weight:800;
  font-size:13px;
  background:#6675e8;
  color:#fff;
}

.brandlabels{
  min-width:0;
  display:flex;
  flex-direction:column;
}

.brandlabels strong{
  font-size:14px;
  line-height:1.1;
  white-space:nowrap;
}

.brandlabels span{
  margin-top:4px;
  font-size:10px;
  color:#8793a6;
  letter-spacing:.13em;
}

.topactions{
  margin-left:auto;
  display:flex !important;
  align-items:center !important;
  gap:7px !important;
  flex:0 0 auto;
}

.topactions form{
  margin:0;
  display:block !important;
}

.bellbtn,
.logoutbtn{
  height:40px;
  margin:0 !important;
  padding:0 12px !important;
  border-radius:11px !important;
  background:#151a23 !important;
  border:1px solid #2a3240 !important;
  box-shadow:none !important;
}

.bellbtn{
  min-width:54px;
}

.logoutbtn{
  min-width:68px;
}

.top>b:before{
  display:none !important;
}

.wrap>div:first-child{
  background:#0d121a !important;
  border:1px solid #202837 !important;
  backdrop-filter:none !important;
  box-shadow:none !important;
}

.card,
.card:hover{
  background:#111722 !important;
  background-image:none !important;
  box-shadow:none !important;
  transform:none !important;
  transition:none !important;
}

.card{
  contain:layout paint;
}

.pill.good:before{
  animation:none !important;
  box-shadow:none !important;
}

.section:not(.hidden){
  animation:none !important;
}

#notifs .card,
#workers .card{
  content-visibility:visible !important;
  contain-intrinsic-size:auto !important;
}

@media(pointer:coarse){
  *,
  *::before,
  *::after{
    animation:none !important;
    transition:none !important;
  }
}

@media(max-width:640px){
  .top{
    padding:11px 12px !important;
  }

  .brandicon{
    width:36px;
    height:36px;
    flex-basis:36px;
  }

  .brandlabels strong{
    font-size:12px;
  }

  .brandlabels span{
    font-size:9px;
  }

  .bellbtn{
    min-width:46px;
    padding:0 8px !important;
  }

  .logoutbtn{
    min-width:58px;
    padding:0 9px !important;
  }
}


/* IDSE_DETAIL_MODAL_V1 */
.worker-card,.report-card{cursor:pointer}
.modal-layer{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:100;display:flex;align-items:center;justify-content:center;padding:18px}
.modal-layer.hidden{display:none}
.modal-box{width:min(760px,100%);max-height:88vh;overflow:auto;background:#0f151f;border:1px solid #2b3546;border-radius:18px;padding:20px;position:relative}
.modal-x{position:absolute;right:12px;top:12px;width:38px;height:38px;padding:0;font-size:23px;line-height:1}
.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:15px}
.detail-item{background:#151c27;border:1px solid #242e3d;border-radius:12px;padding:11px}
.detail-item .k{font-size:11px;color:#8e9bad;text-transform:uppercase;letter-spacing:.07em}
.detail-item .v{margin-top:4px;word-break:break-word}
.progress-shell{height:10px;background:#202837;border-radius:99px;overflow:hidden;margin-top:8px}
.progress-fill{height:100%;background:#6475e8;border-radius:99px}
.activity-list{margin:8px 0 0;padding:0;list-style:none}.activity-list li{padding:8px 0;border-bottom:1px solid #202938}
.report-body{white-space:pre-wrap;word-break:break-word;background:#090d13;border:1px solid #222b39;border-radius:12px;padding:13px;max-height:42vh;overflow:auto;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
@media(max-width:640px){.modal-layer{padding:8px}.modal-box{max-height:92vh;padding:17px}.detail-grid{grid-template-columns:1fr}}


/* IDSE_PANEL_V8_PROJECT_OVERVIEW */
.stats-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px}
.stat-card{background:#111722;border:1px solid #273041;border-radius:16px;padding:14px}
.stat-card .big{font-size:25px;font-weight:800;letter-spacing:-.04em}
.stat-card .small{font-size:12px;color:#94a3b8;margin-top:4px}
.project-main{margin-bottom:12px}.bar{height:9px;background:#202837;border-radius:99px;overflow:hidden;margin-top:8px}.bar>span{display:block;height:100%;background:#6675e8;border-radius:99px}
.progress-columns{display:grid;grid-template-columns:1fr 1fr;gap:12px}.checkpoint-list{display:flex;flex-direction:column;gap:8px;margin-top:10px}.checkpoint-row{display:flex;justify-content:space-between;gap:10px;align-items:center;border-top:1px solid #242c39;padding-top:8px}.status-text{font-size:12px;font-weight:700;text-align:right}
.phase-pipeline{display:flex;gap:8px;overflow-x:auto;padding:2px 0 10px}.phase-chip{flex:0 0 auto;background:#111722;border:1px solid #273041;border-radius:14px;padding:10px 12px;min-width:122px}
.worker-reason{margin-top:9px;padding-top:8px;border-top:1px solid #242c39;color:#b1bccb;font-size:12px;line-height:1.45}
.filter-card{margin-bottom:10px}.filter-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.filter-grid label{font-size:11px;color:#94a3b8;display:flex;flex-direction:column;gap:6px}.filter-grid select{width:100%;background:#0d121a;color:#fff;border:1px solid #303746;border-radius:10px;padding:10px}.status-legend td:first-child{white-space:nowrap;font-weight:700}.task-empty{padding:14px 0;text-align:center}.mini-note{font-size:12px;color:#94a3b8;line-height:1.5;margin-top:6px}
@media(max-width:700px){.stats-grid{grid-template-columns:1fr 1fr}.stats-grid .stat-card:first-child{grid-column:1/-1}.progress-columns{grid-template-columns:1fr}.filter-grid{grid-template-columns:1fr}.tasks-table td:nth-child(4),.tasks-table th:nth-child(4),.tasks-table td:nth-child(5),.tasks-table th:nth-child(5){display:none}.status-legend td:nth-child(2),.status-legend th:nth-child(2){display:table-cell!important}}
</style></head><body>
<div class=top>
<div class=brandbar>
  <div class=brandicon>ID</div>
  <div class=brandlabels>
    <strong>IDSE NETWORK</strong>
    <span>DEVELOPING PANEL</span>
  </div>
</div>
<div class=topactions>
  <button class=bellbtn onclick="showTab('notifications')">🔔 <span id=unread>0</span></button>
  <form method=post action=/logout><button class=logoutbtn>Keluar</button></form>
</div>
</div>
<div class=wrap><div><button onclick="showTab('dashboard')">Dashboard</button> <button onclick="showTab('tasks')">Tasks</button> <button onclick="showTab('reports')">Reports</button> <button onclick="showTab('phases')">Phases</button> <button onclick="showTab('notifications')">Notif</button></div>
<section id=dashboard class=section>
<h2>Ringkasan Proyek</h2>
<div id=projectSummary class=stats-grid></div>
<div id=project class="card project-main"></div>
<h2>Progress Checkpoint</h2>
<div id=checkpointProgress class=progress-columns></div>
<h2>Pipeline Phase</h2>
<div id=phasePipeline class=phase-pipeline></div>
<h2>Workers</h2>
<div id=workers class=grid></div>
<h2>Notifikasi Telegram</h2>
<div id=telegramCard class=card></div>
</section>
<section id=tasks class="section hidden">
<h2>Antrean / Tasks</h2>
<div class="card filter-card"><div class=filter-grid>
<label>Agent<select id=taskAgentFilter onchange=renderTasks()><option value="">Semua Agent</option></select></label>
<label>Status<select id=taskStatusFilter onchange=renderTasks()><option value="">Semua Status</option></select></label>
<label>Checkpoint<select id=taskCheckpointFilter onchange=renderTasks()><option value="">Semua Checkpoint</option></select></label>
</div></div>
<div class=card><table class=tasks-table><thead><tr><th>ID</th><th>Agent</th><th>Status</th><th>Checkpoint</th><th>Percobaan</th></tr></thead><tbody id=taskrows></tbody></table><div id=taskEmpty class="muted task-empty hidden">Tidak ada task yang cocok dengan filter.</div></div>
<h3>Keterangan Status</h3>
<div class=card><table class=status-legend><thead><tr><th>Status</th><th>Keterangan</th></tr></thead><tbody id=statusLegendRows></tbody></table></div>
</section>
<section id=reports class="section hidden"><h2>Reports</h2><div id=reportlist class=grid></div></section>
<section id=phases class="section hidden"><h2>Upload Phase</h2><div class=card><input id=phasefile type=file accept=".md,.zip"> <button onclick=uploadPhase()>Upload & Validate</button><div id=phaseout class=muted></div></div><h3>Uploads</h3><div id=phaselist></div></section>
<section id=notifications class="section hidden"><h2>Notifications</h2><button onclick=readAll()>Tandai semua dibaca</button><div id=notifs></div></section></div>

<div id="detailModal" class="modal-layer hidden" onclick="closeDetail()">
  <div class="modal-box" onclick="event.stopPropagation()">
    <button class="modal-x" onclick="closeDetail()" aria-label="Close">×</button>
    <div id="detailContent">Loading...</div>
  </div>
</div>
<script>
const CSRF='__CSRF__';
async function api(u,o={}){o.headers={...(o.headers||{}),'x-csrf-token':CSRF};let r=await fetch(u,o);if(r.status==401){location='/login';throw Error('login')}let j=await r.json();if(!r.ok)throw Error(j.detail||'error');return j}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

function fmtWIB(v){
  if(!v || v==='-') return '-';
  const d = new Date(v);
  if(Number.isNaN(d.getTime())) return String(v);

  return new Intl.DateTimeFormat('id-ID',{
    timeZone:'Asia/Jakarta',
    day:'2-digit',
    month:'short',
    year:'numeric',
    hour:'2-digit',
    minute:'2-digit',
    second:'2-digit',
    hourCycle:'h23'
  }).format(d).replace(' pukul ', ' • ') + ' WIB';
}

function showTab(id){document.querySelectorAll('section').forEach(x=>x.classList.add('hidden'));document.getElementById(id).classList.remove('hidden')}
let allTasks=[];
const STATUS_MAP={QUEUED:['🕒','Antrean'],RUNNING:['🔵','Sedang dikerjakan'],READY_FOR_AUDIT:['🟣','Siap diaudit'],WAITING_DEPENDENCY:['🔒','Menunggu dependensi'],PASS_CANDIDATE:['🟡','Kandidat lulus'],FINAL_PASS:['✅','Lulus final'],REVISE_REQUIRED:['🔁','Perlu revisi'],REVISE:['🔁','Sedang revisi'],COMPLETED:['✅','Selesai'],BLOCKED:['⛔','Terblokir'],ERROR:['🚨','Error'],WAITING:['⏸️','Menunggu'],AUDITING:['🔍','Sedang audit'],WAITING_REVISION:['🔁','Menunggu revisi'],PAUSED:['⏸️','Dijeda'],OFFLINE:['⚫','Offline'],RECOVERING:['🛠️','Pemulihan'],CANCELLED:['🚫','Dibatalkan'],PENDING:['⚪','Belum dimulai'],ACTIVE:['🚀','Aktif'],VALIDATED:['📦','Tervalidasi']};
function statusLabel(raw){const x=STATUS_MAP[String(raw||'PENDING')]||['ℹ️',String(raw||'-')];return `${x[0]} ${x[1]}`}
function statusClass(raw){if(['FINAL_PASS','COMPLETED','RUNNING','AUDITING','ACTIVE'].includes(raw))return 'good';if(['BLOCKED','ERROR'].includes(raw))return 'bad';return 'warn'}
function populateFilter(id,values,labeler=(x)=>x){const el=document.getElementById(id);const current=el.value;const first=el.options[0]?.outerHTML||'<option value="">Semua</option>';el.innerHTML=first+[...new Set(values.filter(Boolean))].sort().map(v=>`<option value="${esc(v)}">${esc(labeler(v))}</option>`).join('');if([...el.options].some(o=>o.value===current))el.value=current}
function renderTasks(){const agent=document.getElementById('taskAgentFilter')?.value||'';const state=document.getElementById('taskStatusFilter')?.value||'';const cp=document.getElementById('taskCheckpointFilter')?.value||'';const rows=allTasks.filter(x=>(!agent||x.target_agent===agent)&&(!state||x.state===state)&&(!cp||x.checkpoint===cp));taskrows.innerHTML=rows.map(x=>`<tr><td>${esc(x.id)}</td><td>${esc(x.target_agent)}</td><td><span class="pill ${statusClass(x.state)}">${esc(statusLabel(x.state))}</span></td><td>${esc(x.checkpoint||'-')}</td><td>${esc(x.attempts??0)}</td></tr>`).join('');document.getElementById('taskEmpty').classList.toggle('hidden',rows.length>0)}
function checkpointCard(title,items,pct){return `<div class=card><b>${esc(title)}</b><div class=mini-note>${pct}% checkpoint Lulus Final</div><div class=bar><span style="width:${pct}%"></span></div><div class=checkpoint-list>${items.map(x=>`<div class=checkpoint-row><span>${esc(x.checkpoint)}</span><span class=status-text>${esc(statusLabel(x.state))}</span></div>`).join('')}</div></div>`}
async function refresh(){const [p,w,t,n,r,ph,stats,tg]=await Promise.all([api('/api/project'),api('/api/workers'),api('/api/tasks'),api('/api/notifications'),api('/api/reports'),api('/api/phases'),api('/api/project/stats'),api('/api/telegram-status')]);allTasks=t;projectSummary.innerHTML=`<div class=stat-card><div class=big>${esc(stats.overall_percent)}%</div><div class=small>Progress Phase ${esc(stats.current_phase)}</div><div class=bar><span style="width:${stats.overall_percent}%"></span></div></div><div class=stat-card><div class=big>${esc(stats.backend_percent)}%</div><div class=small>Backend</div><div class=bar><span style="width:${stats.backend_percent}%"></span></div></div><div class=stat-card><div class=big>${esc(stats.frontend_percent)}%</div><div class=small>Frontend</div><div class=bar><span style="width:${stats.frontend_percent}%"></span></div></div>`;project.innerHTML=`<b>Phase ${esc(stats.current_phase)} · ${esc(String(stats.phase_status).toUpperCase())}</b><div class=mini-note>Berikutnya: ${esc(stats.next_action)}</div><div class=mini-note>Backend HEAD ${esc(p.backend_git?.head_sha?.slice(0,8)||'-')} · Frontend HEAD ${esc(p.frontend_git?.head_sha?.slice(0,8)||'-')}</div>`;checkpointProgress.innerHTML=checkpointCard('🧠 Backend',stats.backend,stats.backend_percent)+checkpointCard('🖥️ Frontend',stats.frontend,stats.frontend_percent);phasePipeline.innerHTML=stats.phase_pipeline.map(x=>`<div class=phase-chip><b>Phase ${esc(x.phase)}</b><div class=mini-note>${esc(statusLabel(x.state))}</div></div>`).join('');const statWorkers=Object.fromEntries((stats.workers||[]).map(x=>[x.id,x]));workers.innerHTML=w.map(x=>{const sw=statWorkers[x.id]||{};return `<div class="card worker-card" onclick="openWorker('${x.id}')"><b>${esc(x.id==='auditor'?'AUTO AUDITOR':x.id.toUpperCase())}</b> <span class="pill ${statusClass(x.status)}">${esc(statusLabel(x.status))}</span><p>${esc(x.role)}</p><div class=muted>Task: ${esc(x.current_task_id||'-')}<br>Checkpoint: ${esc(x.checkpoint||'-')}<br>HEAD: ${esc((x.head_sha||'').slice(0,8))}<br>Heartbeat: ${esc(fmtWIB(x.last_heartbeat))}</div><div class=worker-reason><b>Keterangan:</b><br>${esc(sw.reason||x.current_activity||'Tidak ada keterangan.')}</div>${['hermes','codex'].includes(x.id)?`<p><button onclick="event.stopPropagation();act('${x.id}','${x.paused?'resume':'pause'}')">${x.paused?'Lanjutkan':'Jeda'}</button> <button onclick="event.stopPropagation();act('${x.id}','retry')">Ulangi</button></p>`:''}</div>`}).join('');telegramCard.innerHTML=`<b>${tg.configured?'✅ Telegram aktif':'⚠️ Telegram belum aktif'}</b><div class=mini-note>Status service: ${esc(statusLabel(tg.status))}</div><div class=mini-note>Event penting belum terkirim: ${esc(tg.pending_important_events)}</div><div class=mini-note>${esc(tg.last_log||'Belum ada log notifier.')}</div>${tg.configured?'<p><button onclick="testTelegram()">Kirim notifikasi tes</button></p>':'<div class=mini-note>Notifier memerlukan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di environment service. Nilai rahasia tidak ditampilkan di panel.</div>'}`;populateFilter('taskAgentFilter',allTasks.map(x=>x.target_agent),x=>x.toUpperCase());populateFilter('taskStatusFilter',allTasks.map(x=>x.state),statusLabel);populateFilter('taskCheckpointFilter',allTasks.map(x=>x.checkpoint));renderTasks();statusLegendRows.innerHTML=(stats.status_legend||[]).map(x=>`<tr><td>${esc(x.icon+' '+x.label)}</td><td>${esc(x.detail)}</td></tr>`).join('');document.getElementById('unread').textContent=n.filter(x=>!x.read_at).length;notifs.innerHTML=n.slice(0,30).map(x=>`<div class=card style="margin-top:8px"><b>${esc(x.severity)} · ${esc(x.title)}</b><div>${esc(x.message)}</div><div class=muted>🕒 ${esc(fmtWIB(x.timestamp))}</div></div>`).join('');reportlist.innerHTML=r.slice(0,30).map(x=>`<div class="card report-card" onclick="openReport('${x.id}')"><b>${esc(x.name)}</b><p class=muted>${esc(x.agent)}<br>Masuk panel: ${esc(fmtWIB(x.first_seen_at))}</p><button onclick="event.stopPropagation();openReport('${x.id}')">Lihat detail</button></div>`).join('');phaselist.innerHTML=ph.map(x=>`<div class=card style="margin-top:8px"><b>Phase ${x.phase}</b> · ${esc(statusLabel(x.status))}<br><span class=muted>${esc(x.master_spec_name)}</span>${x.status==='VALIDATED'?`<p><button onclick="activate('${x.id}')">Setujui / antrekan Phase</button></p>`:''}</div>`).join('')}
async function testTelegram(){try{let x=await api('/api/telegram-test',{method:'POST'});alert(x.message||'Event tes dibuat');setTimeout(refresh,1200)}catch(e){alert(e.message)}}

let detailTimer=null;
let detailKind=null;
let detailId=null;

function closeDetail(){
  document.getElementById('detailModal').classList.add('hidden');
  if(detailTimer){clearInterval(detailTimer);detailTimer=null}
  detailKind=null;detailId=null;
}

function showDetail(html){
  document.getElementById('detailContent').innerHTML=html;
  document.getElementById('detailModal').classList.remove('hidden');
}

function durationSince(v){
  if(!v)return '-';
  const ms=Date.now()-new Date(v).getTime();
  if(!Number.isFinite(ms)||ms<0)return '-';
  const sec=Math.floor(ms/1000), min=Math.floor(sec/60), hr=Math.floor(min/60);
  if(hr)return `${hr}j ${min%60}m`;
  if(min)return `${min}m ${sec%60}d`;
  return `${sec}d`;
}

async function openWorker(id){
  detailKind='worker';detailId=id;
  await refreshWorkerDetail();
  if(detailTimer)clearInterval(detailTimer);
  detailTimer=setInterval(refreshWorkerDetail,4000);
}

async function refreshWorkerDetail(){
  if(detailKind!=='worker'||!detailId)return;
  const d=await api(`/api/workers/${detailId}/detail`);
  const w=d.worker,t=d.task,p=d.progress_pct||0;
  const name=w.id==='auditor'?'AUTO AUDITOR':String(w.id).toUpperCase();
  const events=(d.events||[]).map(e=>`<li><b>${esc(e.title)}</b><br><span class=muted>${esc(e.message)} · ${esc(fmtWIB(e.timestamp))}</span></li>`).join('');
  showDetail(`
    <h2 style="margin-top:0">${esc(name)}</h2>
    <div><span class="pill ${['ERROR','BLOCKED','OFFLINE'].includes(w.status)?'bad':['RECOVERING','PAUSED','WAITING_REVISION'].includes(w.status)?'warn':'good'}">${esc(w.status)}</span></div>
    <p class=muted>Estimasi progress operasional — bukan progress internal reasoning model.</p>
    <b>${p}%</b>
    <div class=progress-shell><div class=progress-fill style="width:${p}%"></div></div>
    <div class=detail-grid>
      <div class=detail-item><div class=k>Stage</div><div class=v>${esc(w.current_stage||'-')}</div></div>
      <div class=detail-item><div class=k>Aktivitas</div><div class=v>${esc(w.current_activity||'-')}</div></div>
      <div class=detail-item><div class=k>Task</div><div class=v>${esc(w.current_task_id||'-')}</div></div>
      <div class=detail-item><div class=k>Checkpoint</div><div class=v>${esc(w.checkpoint||'-')}</div></div>
      <div class=detail-item><div class=k>Branch</div><div class=v>${esc(w.branch||'-')}</div></div>
      <div class=detail-item><div class=k>HEAD</div><div class=v>${esc(w.head_sha||'-')}</div></div>
      <div class=detail-item><div class=k>Started</div><div class=v>${esc(fmtWIB(w.task_started_at))}</div></div>
      <div class=detail-item><div class=k>Elapsed</div><div class=v>${esc(durationSince(w.task_started_at))}</div></div>
      <div class=detail-item><div class=k>Attempts</div><div class=v>${esc(t?.attempts??w.retry_attempt??0)}</div></div>
      <div class=detail-item><div class=k>Heartbeat</div><div class=v>${esc(fmtWIB(w.last_heartbeat))}</div></div>
    </div>
    <h3>Recent activity</h3>
    <ul class=activity-list>${events||'<li class=muted>Belum ada event.</li>'}</ul>
  `);
}

async function openReport(id){
  detailKind='report';detailId=id;
  if(detailTimer){clearInterval(detailTimer);detailTimer=null}
  const d=await api(`/api/reports/${id}`);
  showDetail(`
    <h2 style="margin-top:0">Report Detail</h2>
    <div class=detail-grid>
      <div class=detail-item><div class=k>Nama</div><div class=v>${esc(d.name)}</div></div>
      <div class=detail-item><div class=k>Agent</div><div class=v>${esc(d.agent)}</div></div>
      <div class=detail-item><div class=k>Status</div><div class=v>${esc(d.status)}</div></div>
      <div class=detail-item><div class=k>Dibuat</div><div class=v>${esc(fmtWIB(d.created_at))}</div></div>
      <div class=detail-item><div class=k>Masuk panel</div><div class=v>${esc(fmtWIB(d.first_seen_at))}</div></div>
      <div class=detail-item><div class=k>Terakhir berubah</div><div class=v>${esc(fmtWIB(d.modified_at))}</div></div>
    </div>
    <p><a href="${esc(d.download_url)}"><button>Download report</button></a></p>
    <h3>Isi report</h3>
    <pre class=report-body>${esc(d.content)}${d.truncated?'\\n\\n[Preview dipotong. Download untuk file lengkap.]':''}</pre>
  `);
}

async function act(w,a){try{await api(`/api/workers/${w}/${a}`,{method:'POST'});refresh()}catch(e){alert(e.message)}}
async function readAll(){await api('/api/notifications/read-all',{method:'POST'});refresh()}
async function uploadPhase(){let f=phasefile.files[0];if(!f)return;let fd=new FormData();fd.append('file',f);try{let x=await api('/api/phases/upload',{method:'POST',body:fd});phaseout.textContent=`Validated Phase ${x.phase}: ${x.master_spec}`;refresh()}catch(e){phaseout.textContent='ERROR: '+e.message}}
async function activate(id){if(!confirm('Activate phase ini dan queue task manifest yang valid?'))return;try{await api(`/api/phases/${id}/activate`,{method:'POST'});refresh()}catch(e){alert(e.message)}}
let lastScroll=0;
addEventListener('scroll',()=>{lastScroll=Date.now()},{passive:true});
refresh();
setInterval(()=>{
  if(!document.hidden && Date.now()-lastScroll>2500) refresh()
},15000);
</script></body></html>"""
