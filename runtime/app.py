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


def report_index():
    result = []
    roots = [
        ("backend", BACKEND_WORKSPACE / "docs/reports"),
        ("frontend", FRONTEND_WORKSPACE / "docs/reports"),
        ("orchestrator", ROOT / "audit"),
    ]
    for agent, base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*.md"):
            report_id = hashlib.sha1(str(path).encode()).hexdigest()[:16]
            result.append(
                {
                    "id": report_id,
                    "agent": agent,
                    "name": path.name,
                    "path": str(path),
                    "mtime": path.stat().st_mtime,
                }
            )
    return sorted(result, key=lambda x: x["mtime"], reverse=True)


@app.get("/api/reports")
def reports(request: Request):
    require(request)
    return report_index()


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

<style>

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

</style></style></head><body>
<div class=top><b>IDSE NETWORK DEVELOPING PANEL</b><div><button onclick="showTab('notifications')">🔔 <span id=unread>0</span></button> <form style=display:inline method=post action=/logout><button>Keluar</button></form></div></div>
<div class=wrap><div><button onclick="showTab('dashboard')">Dashboard</button> <button onclick="showTab('tasks')">Tasks</button> <button onclick="showTab('reports')">Reports</button> <button onclick="showTab('phases')">Phases</button> <button onclick="showTab('notifications')">Notif</button></div>
<section id=dashboard class=section><h2>Workers</h2><div id=workers class=grid></div><h2>Project</h2><div id=project class=card></div></section>
<section id=tasks class="section hidden"><h2>Queue / Tasks</h2><div class=card><table><thead><tr><th>ID</th><th>Agent</th><th>Status</th><th>Checkpoint</th><th>Attempts</th></tr></thead><tbody id=taskrows></tbody></table></div></section>
<section id=reports class="section hidden"><h2>Reports</h2><div id=reportlist class=grid></div></section>
<section id=phases class="section hidden"><h2>Upload Phase</h2><div class=card><input id=phasefile type=file accept=".md,.zip"> <button onclick=uploadPhase()>Upload & Validate</button><div id=phaseout class=muted></div></div><h3>Uploads</h3><div id=phaselist></div></section>
<section id=notifications class="section hidden"><h2>Notifications</h2><button onclick=readAll()>Tandai semua dibaca</button><div id=notifs></div></section></div>
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
async function refresh(){let [p,w,t,n,r,ph]=await Promise.all([api('/api/project'),api('/api/workers'),api('/api/tasks'),api('/api/notifications'),api('/api/reports'),api('/api/phases')]);project.innerHTML=`Phase <b>${esc(p.current_phase)}</b> · ${esc(p.phase_status)}<br><span class=muted>Backend ${esc(p.backend_git?.head_sha?.slice(0,8))} · Frontend ${esc(p.frontend_git?.head_sha?.slice(0,8))}</span>`;workers.innerHTML=w.map(x=>`<div class=card><b>${esc(x.id==='auditor'?'AUTO AUDITOR':x.id.toUpperCase())}</b> <span class="pill ${['ERROR','BLOCKED','OFFLINE'].includes(x.status)?'bad':['RECOVERING','PAUSED'].includes(x.status)?'warn':'good'}">${esc(x.status)}</span><p>${esc(x.role)}</p><div class=muted>Task: ${esc(x.current_task_id||'-')}<br>Checkpoint: ${esc(x.checkpoint||'-')}<br>HEAD: ${esc((x.head_sha||'').slice(0,8))}<br>Heartbeat: ${esc(fmtWIB(x.last_heartbeat))}</div>${['hermes','codex'].includes(x.id)?`<p><button onclick="act('${x.id}','${x.paused?'resume':'pause'}')">${x.paused?'Resume':'Pause'}</button> <button onclick="act('${x.id}','retry')">Retry</button></p>`:''}</div>`).join('');taskrows.innerHTML=t.map(x=>`<tr><td>${esc(x.id)}</td><td>${esc(x.target_agent)}</td><td>${esc(x.state)}</td><td>${esc(x.checkpoint||'')}</td><td>${esc(x.attempts)}</td></tr>`).join('');document.getElementById('unread').textContent=n.filter(x=>!x.read_at).length;notifs.innerHTML=n.slice(0,80).map(x=>`<div class=card style="margin-top:8px"><b>${esc(x.severity)} · ${esc(x.title)}</b><div>${esc(x.message)}</div><div class=muted>🕒 ${esc(fmtWIB(x.timestamp))}</div></div>`).join('');reportlist.innerHTML=r.slice(0,60).map(x=>`<div class=card><b>${esc(x.name)}</b><p class=muted>${esc(x.agent)}</p><a href="/api/reports/${x.id}/download"><button>Download</button></a></div>`).join('');phaselist.innerHTML=ph.map(x=>`<div class=card style="margin-top:8px"><b>Phase ${x.phase}</b> · ${esc(x.status)}<br><span class=muted>${esc(x.master_spec_name)}</span>${x.status==='VALIDATED'?`<p><button onclick="activate('${x.id}')">Activate Phase</button></p>`:''}</div>`).join('')}
async function act(w,a){try{await api(`/api/workers/${w}/${a}`,{method:'POST'});refresh()}catch(e){alert(e.message)}}
async function readAll(){await api('/api/notifications/read-all',{method:'POST'});refresh()}
async function uploadPhase(){let f=phasefile.files[0];if(!f)return;let fd=new FormData();fd.append('file',f);try{let x=await api('/api/phases/upload',{method:'POST',body:fd});phaseout.textContent=`Validated Phase ${x.phase}: ${x.master_spec}`;refresh()}catch(e){phaseout.textContent='ERROR: '+e.message}}
async function activate(id){if(!confirm('Activate phase ini dan queue task manifest yang valid?'))return;try{await api(`/api/phases/${id}/activate`,{method:'POST'});refresh()}catch(e){alert(e.message)}}
refresh();setInterval(refresh,10000);
</script></body></html>"""
