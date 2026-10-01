# FINAL REVIEW PROTOCOL

## Authority

- Hermes and Codex implement engineering tasks.
- AUTO AUDITOR performs automated pre-audit.
- ChatGPT performs independent FINAL REVIEW.
- A dependent audit MUST wait until the dependency task state is `FINAL_PASS`.

## VPS → GitHub

The GitHub Audit Bridge publishes these files to branch `orchestration`:

- `state/audit-index.json`
- `state/runtime-snapshot.json`
- `audit/**/*.md`
- revision task files under `inbox/hermes/` and `inbox/codex/`

A checkpoint is eligible for ChatGPT final review when its audit state is `PASS_CANDIDATE`.

## ChatGPT → GitHub

ChatGPT writes exactly one JSON file per authoritative SHA:

`state/final-reviews/<CHECKPOINT>-<SHA8>.json`

Required JSON shape:

{
  "schema_version": 1,
  "checkpoint": "P2-D",
  "phase": 2,
  "source_agent": "hermes",
  "authoritative_sha": "40-hex authoritative source SHA",
  "audit_task_id": "AUDIT-P2-D-d797720",
  "auto_verdict": "PASS_CANDIDATE",
  "verdict": "FINAL_PASS",
  "reviewer": "ChatGPT",
  "reviewed_at": "ISO-8601 UTC timestamp",
  "summary": "Concise final-review rationale.",
  "findings": []
}

Allowed verdicts:
- FINAL_PASS
- REVISE
- BLOCKED

For REVISE, `findings` must contain concrete actionable findings.
Do not include private chain-of-thought.

## GitHub → VPS

Final Review Sync polls GitHub and applies the result:

- FINAL_PASS → audit task becomes `FINAL_PASS`; dependent audit may continue.
- REVISE → audit task becomes `REVISE_REQUIRED`; `REV-FINAL-*` is queued for the source agent.
- BLOCKED → audit task becomes `BLOCKED`; Owner is notified.
