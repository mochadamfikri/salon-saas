# Automated Audit — P3-D

- Source agent: codex
- Source branch: feature/phase-2-web-codex
- Base SHA: 93c463c35cef2f0ef17628a278fae7d526eed673
- Audited SHA: ccdcc3782a401736347ee5a685d070e743e4b04a
- Generated: 2026-10-02T04:21:57.916595+00:00

**P3-D Audit**
- Checkpoint: P3-D; audited SHA: `ccdcc3782a401736347ee5a685d070e743e4b04a`
- Scope: reviewed the pinned diff, appointment BFF routes, calendar page/component, transport contracts, and available frontend tests.
- Verification: trusted host reports Vitest **PASS** (29 files, 198 tests), TypeScript **PASS**, ESLint **PASS**, and production build **PASS**. No separate audit-run tests.

**Findings**
- **Major — Required calendar views are incomplete.** The UI implements daily navigation and a table only; there is no week view, despite P3-D explicitly requiring a mobile day/week calendar/list. Evidence: `apps/web/src/components/salon/AppointmentCalendar.tsx` provides a single-date query and table with no view selector or week navigation.
- **Major — Available-time UX is missing.** Appointment creation accepts an arbitrary `datetime-local` value and does not retrieve or present availability for the selected staff/service. Backend enforcement remains authoritative, but the P3-D requirement includes available-time UX. Evidence: the creation form in `apps/web/src/components/salon/AppointmentCalendar.tsx` submits the entered time directly.

**Security and contract review**
- Appointment calls use `authorizedCall` and session handling in the BFF; access tokens are passed server-side and are not returned in browser JSON.
- Salon/resource authorization and booking eligibility remain backend-authoritative. The UI’s filtered picker options are UX-only.
- BFF maps malformed writes to 422 and preserves backend failures through the shared error mapping; actions are allowlisted. No tenant/RBAC bypass or confirmed token-boundary regression found in the inspected changes.
- No frontend tests specific to the new appointment routes/calendar were found.

**Residual notes**
- The reported broad frontend gates passed on the pinned SHA. Backend authorization and booking-engine correctness are outside this frontend diff; this audit found no frontend evidence contradicting their contracts.

Verdict is **REVISE**: required week-view and available-time UX are absent from the checkpoint implementation.

AUDIT_VERDICT: REVISE
AUDITED_SHA: ccdcc3782a401736347ee5a685d070e743e4b04a
FINDINGS_COUNT: 2