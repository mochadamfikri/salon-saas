from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
import urllib.request

from common import db, init_db, now_iso, update_worker

POLL = int(os.environ.get("NOTIFIER_POLL_SECONDS", "15"))
LEVELS = {
    x.strip()
    for x in os.environ.get(
        "TELEGRAM_LEVELS", "SUCCESS,WARNING,CRITICAL,OWNER_ACTION_REQUIRED"
    ).split(",")
    if x.strip()
}
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")


def safe_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"Telegram HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return f"Telegram network error: {exc.reason}"
    return f"Telegram send error: {type(exc).__name__}"


def send(text: str) -> bool:
    data = urllib.parse.urlencode(
        {"chat_id": CHAT, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return 200 <= response.status < 300


def main() -> None:
    init_db()
    while True:
        try:
            configured = bool(TOKEN and CHAT)
            if not configured:
                update_worker(
                    "notifier",
                    status="WAITING",
                    current_stage="Telegram belum dikonfigurasi",
                    current_activity=(
                        "Menunggu TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID "
                        "di environment service"
                    ),
                    progress_pct=0,
                    last_log="Telegram notifier belum dikonfigurasi",
                )
                time.sleep(POLL)
                continue

            update_worker(
                "notifier",
                status="RUNNING",
                current_stage="Telegram aktif",
                current_activity="Menunggu event penting",
                progress_pct=100,
            )

            con = db()
            rows = con.execute(
                "SELECT * FROM events WHERE telegram_sent_at IS NULL ORDER BY timestamp LIMIT 50"
            ).fetchall()

            delivery_failed = False
            for row in rows:
                if row["severity"] not in LEVELS:
                    con.execute(
                        "UPDATE events SET telegram_sent_at=? WHERE id=?",
                        (now_iso(), row["id"]),
                    )
                    continue

                icon = {
                    "SUCCESS": "✅",
                    "WARNING": "⚠️",
                    "CRITICAL": "🚨",
                    "OWNER_ACTION_REQUIRED": "🔴",
                }.get(row["severity"], "ℹ️")
                text = f"{icon} SALON SAAS — {row['title']}\n\n{row['message']}"
                if row["phase"] is not None:
                    text += f"\nPhase: {row['phase']}"
                if row["checkpoint"]:
                    text += f"\nCheckpoint: {row['checkpoint']}"
                if row["task_id"]:
                    text += f"\nTask: {row['task_id']}"

                try:
                    if not send(text):
                        raise RuntimeError("Telegram API returned non-success")
                except Exception as exc:
                    err = safe_error(exc)
                    update_worker(
                        "notifier",
                        status="ERROR",
                        current_stage="Pengiriman Telegram gagal",
                        current_activity="Event dipertahankan dan akan dicoba ulang",
                        progress_pct=0,
                        last_log=err,
                    )
                    delivery_failed = True
                    break

                # Mark sent ONLY after actual successful delivery.
                con.execute(
                    "UPDATE events SET telegram_sent_at=? WHERE id=?",
                    (now_iso(), row["id"]),
                )

            con.commit()
            con.close()

            if delivery_failed:
                time.sleep(max(POLL, 30))
                continue

            update_worker(
                "notifier",
                status="RUNNING",
                current_stage="Telegram aktif",
                current_activity="Semua event penting sudah terkirim",
                progress_pct=100,
                last_log="Telegram notifier sehat",
            )
            time.sleep(POLL)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            update_worker(
                "notifier",
                status="ERROR",
                current_stage="Notifier error",
                current_activity="Akan mencoba ulang otomatis",
                progress_pct=0,
                last_log=safe_error(exc),
            )
            time.sleep(30)


if __name__ == "__main__":
    main()
