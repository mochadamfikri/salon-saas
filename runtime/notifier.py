from __future__ import annotations

import os
import time
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


def send(text: str) -> bool:
    data = urllib.parse.urlencode(
        {"chat_id": CHAT, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return 200 <= response.status < 300


def main() -> None:
    init_db()
    while True:
        try:
            configured = bool(TOKEN and CHAT)
            update_worker("notifier", status="RUNNING" if configured else "WAITING")
            if not configured:
                time.sleep(POLL)
                continue

            con = db()
            rows = con.execute(
                "SELECT * FROM events WHERE telegram_sent_at IS NULL ORDER BY timestamp LIMIT 50"
            ).fetchall()
            for row in rows:
                if row["severity"] in LEVELS:
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
                        send(text)
                    except Exception:
                        pass
                con.execute(
                    "UPDATE events SET telegram_sent_at=? WHERE id=?",
                    (now_iso(), row["id"]),
                )
            con.commit()
            con.close()
            time.sleep(POLL)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            update_worker("notifier", status="ERROR", last_log=str(exc))
            time.sleep(30)


if __name__ == "__main__":
    main()
