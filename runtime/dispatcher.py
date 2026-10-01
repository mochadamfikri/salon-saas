from __future__ import annotations

import os
import re
import time
import traceback
from pathlib import Path
from typing import Any

from common import FRONTEND_WORKSPACE, ROOT, db, emit, git_info, init_db, now_iso, register_task

POLL = int(os.environ.get("PHASE_DISPATCHER_POLL_SECONDS", "12"))
FRONTEND_BRANCH = "feature/phase-2-web-codex"

CHECKPOINTS = [
    {
        "checkpoint": "P2-C",
        "backend_gate": None,
        "frontend_task": "FE-P2-C",
        "frontend_audit": "AUDIT-FE-P2-C",
        "report": "docs/reports/codex-p2c-staff-profile-frontend.md",
        "title": "Staff Profile + Staff-Service Assignment Frontend",
    },
    {
        "checkpoint": "P2-D",
        "backend_gate": "AUDIT-P2-D-d797720",
        "frontend_task": "FE-P2-D",
        "frontend_audit": "AUDIT-FE-P2-D",
        "report": "docs/reports/codex-p2d-weekly-availability-frontend.md",
        "title": "Staff Weekly Availability Frontend",
    },
    {
        "checkpoint": "P2-E",
        "backend_gate": "AUDIT-P2-E-df897f9",
        "frontend_task": "FE-P2-E",
        "frontend_audit": "AUDIT-FE-P2-E",
        "report": "docs/reports/codex-p2e-customer-records-frontend.md",
        "title": "Customer Records Frontend",
    },
]


def log(msg: str) -> None:
    p = ROOT / "runtime/logs/dispatcher.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {msg}\n")


def one(sql: str, args: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    con = db()
    row = con.execute(sql, args).fetchone()
    con.close()
    return dict(row) if row else None


def ensure_schema() -> None:
    con = db()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_checkpoints (
          phase INTEGER NOT NULL,
          checkpoint TEXT NOT NULL,
          backend_state TEXT NOT NULL DEFAULT 'PENDING',
          frontend_state TEXT NOT NULL DEFAULT 'PENDING',
          frontend_task_id TEXT,
          frontend_audit_task_id TEXT,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(phase, checkpoint)
        )
        """
    )
    for item in CHECKPOINTS:
        con.execute(
            """
            INSERT OR IGNORE INTO workflow_checkpoints
            (phase,checkpoint,backend_state,frontend_state,frontend_task_id,frontend_audit_task_id,updated_at)
            VALUES(2,?,?,?,?,?,?)
            """,
            (
                item["checkpoint"],
                "PENDING",
                "PENDING",
                item["frontend_task"],
                item["frontend_audit"],
                now_iso(),
            ),
        )
    con.commit()
    con.close()


def get_task(task_id: str) -> dict[str, Any] | None:
    return one("SELECT * FROM tasks WHERE id=?", (task_id,))


def backend_ready(item: dict[str, Any]) -> bool:
    if item["backend_gate"] is None:
        # P2-C backend was already independently FINAL PASS before the control-plane DB existed.
        return True
    row = get_task(item["backend_gate"])
    return bool(row and row["state"] == "FINAL_PASS")


def previous_frontend_final(index: int) -> bool:
    # Frontend checkpoint berikutnya hanya boleh terbuka setelah audit frontend sebelumnya FINAL_PASS.
    if index == 0:
        return True
    prev_audit = get_task(CHECKPOINTS[index - 1]["frontend_audit"])
    return bool(prev_audit and prev_audit["state"] == "FINAL_PASS")


def set_task_state(task_id: str, state: str) -> None:
    con = db()
    con.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    con.commit()
    con.close()


def enforce_frontend_dependencies() -> None:
    # Tahan task yang belum eligible. Task RUNNING tidak dibunuh agar WIP tetap aman.
    for index, item in enumerate(CHECKPOINTS):
        if index == 0:
            continue
        eligible = backend_ready(item) and previous_frontend_final(index)
        impl = get_task(item["frontend_task"])
        audit = get_task(item["frontend_audit"])

        if not eligible:
            if impl and impl["state"] == "QUEUED":
                set_task_state(item["frontend_task"], "WAITING_DEPENDENCY")
            if audit and audit["state"] == "QUEUED":
                set_task_state(item["frontend_audit"], "WAITING_DEPENDENCY")
        else:
            if impl and impl["state"] == "WAITING_DEPENDENCY":
                set_task_state(item["frontend_task"], "QUEUED")
            if audit and audit["state"] == "WAITING_DEPENDENCY":
                set_task_state(item["frontend_audit"], "QUEUED")


def parse_base_sha(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    m = re.search(r"(?mi)^\s*BASE_SHA\s*:\s*([0-9a-f]{7,40})\s*$", p.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def checkpoint_details(cp: str) -> str:
    if cp == "P2-C":
        return """
CHECKPOINT CONTRACT:
- Staff profile list/detail/create/edit using the audited backend contract.
- Owner/Manager create profiles from active memberships and update any same-tenant profile.
- Staff reads same-tenant profiles and edits only own display_name, phone, bio, photo_url.
- is_bookable is Owner/Manager only; membership_id immutable.
- Service assignment/unassignment Owner/Manager only; Staff read-only.
- No StaffProfile hard-delete UI.
- Preserve backend 404/409/422 semantics through BFF/UI.
"""
    if cp == "P2-D":
        return """
CHECKPOINT CONTRACT:
- Weekly availability display plus add/edit/delete slot UI.
- Owner/Manager manage any same-tenant staff profile.
- Staff reads same-tenant schedules and mutates only own profile.
- day_of_week 0..6; start_time < end_time.
- Overlap conflicts display 409; adjacent slots remain valid.
- No booking or appointment engine.
"""
    return """
CHECKPOINT CONTRACT:
- Customer list/create/detail/update; no DELETE UI.
- Owner/Manager/Staff all create/read/update.
- full_name required/trimmed/nonblank; PATCH omission unchanged and null rejected.
- email trim/lowercase and nullable/clearable.
- phone trim and nullable/clearable without over-strict country validation.
- notes nullable/clearable.
- Duplicate email/phone allowed; no auto-merge/dedup rejection.
- Support full-name-only walk-in customer.
- Tenant-scoped BFF; no ownership spoofing.
"""


def create_frontend_task(item: dict[str, Any]) -> None:
    info = git_info(FRONTEND_WORKSPACE)
    if info["branch"] != FRONTEND_BRANCH:
        raise RuntimeError(f"Codex branch {info['branch']!r} != {FRONTEND_BRANCH!r}")
    base = info["head_sha"]
    if not base:
        raise RuntimeError("Codex HEAD unavailable")

    body = f"""TARGET_AGENT: CODEX
TASK_ID: {item['frontend_task']}
PHASE: 2
CHECKPOINT: {item['checkpoint']}
TYPE: implementation
PRIORITY: 20
BASE_SHA: {base}
SOURCE_BRANCH: {FRONTEND_BRANCH}
STATUS: QUEUED

Implement {item['checkpoint']} — {item['title']}.

MANDATORY:
- Work only in /home/ubuntu/salon-saas-frontend on branch {FRONTEND_BRANCH}.
- Backend is read-only source of truth.
- Browser -> Next.js BFF -> FastAPI; keep tokens server-side/HttpOnly.
- Preserve Phase 1 and P2-B audited behavior.
- No merge/deploy/force-push/backend edits/later-phase scope.
- Run relevant Vitest + full frontend tests, TypeScript, ESLint, and production build.
- Commit and push the frontend branch.
- Write completion report exactly at {item['report']}.
- Exit successfully only when READY_FOR_AUDIT.
{checkpoint_details(item['checkpoint'])}
"""
    path = ROOT / "inbox/codex" / f"{item['frontend_task']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(body, encoding="utf-8")
    register_task(path, "codex")
    emit(
        "dispatcher", "frontend.queued", "INFO",
        f"Frontend queued: {item['checkpoint']}",
        f"{item['frontend_task']} dispatched automatically.",
        phase=2, checkpoint=item["checkpoint"], task_id=item["frontend_task"],
        metadata={"base_sha": base},
    )
    log(f"QUEUED {item['frontend_task']} base={base[:8]}")


def create_frontend_audit(item: dict[str, Any], impl: dict[str, Any]) -> None:
    info = git_info(FRONTEND_WORKSPACE)
    audited = info["head_sha"]
    base = parse_base_sha(impl.get("task_path"))
    if not audited or not base:
        raise RuntimeError(f"Unable to resolve frontend audit SHAs for {item['checkpoint']}")

    body = f"""TARGET_AGENT: AUDITOR
TASK_ID: {item['frontend_audit']}
PHASE: 2
CHECKPOINT: {item['checkpoint']}
TYPE: audit
PRIORITY: 30
SOURCE_AGENT: CODEX
SOURCE_BRANCH: {FRONTEND_BRANCH}
BASE_SHA: {base}
AUDITED_SHA: {audited}
REPORT_SOURCE: {item['report']}
STATUS: QUEUED

Independently audit the frontend checkpoint against PROJECT_RULES, CODEX_RULES,
PHASE2_MASTER_SPEC and the approved backend contract. Inspect actual diff/source/tests.
Verify BFF/session security, tenant behavior, role-aware UX, validation/null semantics,
error handling, scope discipline and regression risk. Do not implement fixes.
"""
    path = ROOT / "inbox/auditor" / f"{item['frontend_audit']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(body, encoding="utf-8")
    register_task(path, "auditor")
    emit(
        "dispatcher", "frontend.audit_queued", "INFO",
        f"Frontend audit queued: {item['checkpoint']}",
        f"{item['frontend_audit']} auditing {audited[:8]}.",
        phase=2, checkpoint=item["checkpoint"], task_id=item["frontend_audit"],
        metadata={"base_sha": base, "audited_sha": audited},
    )
    log(f"AUDIT QUEUED {item['frontend_audit']} sha={audited[:8]}")


def close_ready_sources() -> None:
    con = db()
    cps = con.execute(
        "SELECT checkpoint FROM tasks WHERE target_agent='auditor' AND state='FINAL_PASS'"
    ).fetchall()
    for row in cps:
        con.execute(
            "UPDATE tasks SET state='COMPLETED' "
            "WHERE checkpoint=? AND target_agent IN ('hermes','codex') "
            "AND state='READY_FOR_AUDIT'",
            (row["checkpoint"],),
        )
    con.commit()
    con.close()


def sync_states() -> None:
    con = db()
    for item in CHECKPOINTS:
        bstate = "FINAL_PASS" if backend_ready(item) else "PENDING"
        impl = con.execute("SELECT state FROM tasks WHERE id=?", (item["frontend_task"],)).fetchone()
        audit = con.execute("SELECT state FROM tasks WHERE id=?", (item["frontend_audit"],)).fetchone()
        fstate = audit["state"] if audit else (impl["state"] if impl else "PENDING")
        con.execute(
            "UPDATE workflow_checkpoints SET backend_state=?,frontend_state=?,updated_at=? "
            "WHERE phase=2 AND checkpoint=?",
            (bstate, fstate, now_iso(), item["checkpoint"]),
        )
    con.commit()
    con.close()


def maybe_phase2_ready() -> None:
    con = db()
    rows = con.execute(
        "SELECT backend_state,frontend_state FROM workflow_checkpoints WHERE phase=2"
    ).fetchall()
    ready = len(rows) == 3 and all(
        r["backend_state"] == "FINAL_PASS" and r["frontend_state"] == "FINAL_PASS"
        for r in rows
    )
    exists = con.execute(
        "SELECT 1 FROM events WHERE type='phase2.engineering_ready' LIMIT 1"
    ).fetchone()
    con.close()
    if ready and not exists:
        emit(
            "dispatcher", "phase2.engineering_ready", "SUCCESS",
            "Phase 2 engineering checkpoints complete",
            "Backend and frontend P2-C/P2-D/P2-E are FINAL_PASS. Run Phase 2 integration closure next.",
            phase=2, checkpoint="PHASE2-CLOSURE",
        )
        log("PHASE2 ENGINEERING READY")


def dispatch_once() -> None:
    ensure_schema()
    close_ready_sources()

    enforce_frontend_dependencies()

    for index, item in enumerate(CHECKPOINTS):
        eligible = backend_ready(item) and previous_frontend_final(index)

        impl = get_task(item["frontend_task"])
        impl_path_missing = bool(
            impl
            and impl["state"] in ("QUEUED", "WAITING_DEPENDENCY", "REVISE")
            and not Path(impl["task_path"]).exists()
        )

        # Self-heal SQLite/file drift: a queued DB task is not executable if
        # the inbox markdown was lost by maintenance/stash/cleanup.
        if eligible and (not impl or impl_path_missing):
            create_frontend_task(item)

        impl = get_task(item["frontend_task"])
        audit = get_task(item["frontend_audit"])
        audit_path_missing = bool(
            audit
            and audit["state"] in ("QUEUED", "WAITING_DEPENDENCY")
            and not Path(audit["task_path"]).exists()
        )

        if (
            eligible
            and impl
            and impl["state"] == "READY_FOR_AUDIT"
            and (not audit or audit_path_missing)
        ):
            create_frontend_audit(item, impl)

    enforce_frontend_dependencies()

    close_ready_sources()
    sync_states()
    maybe_phase2_ready()


def main() -> None:
    init_db()
    ensure_schema()
    emit(
        "dispatcher", "dispatcher.online", "INFO",
        "Phase Dispatcher online",
        "Automatic backend-to-frontend Phase 2 dispatch started.",
        phase=2,
    )
    while True:
        try:
            dispatch_once()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            log("ERROR " + repr(exc) + " | " + traceback.format_exc()[-2200:])
            emit(
                "dispatcher", "dispatcher.error", "CRITICAL",
                "Phase Dispatcher error", str(exc), phase=2,
            )
        time.sleep(POLL)


if __name__ == "__main__":
    main()
