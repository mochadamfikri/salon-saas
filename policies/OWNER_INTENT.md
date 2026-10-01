# OWNER INTENT — Salon SaaS

The Owner is Product Authority. Routine development must be autonomous.

- Eligible work starts automatically; workers must not wait without an explicit dependency reason.
- Backend checkpoints may pipeline within the same phase after the previous backend checkpoint FINAL_PASS.
- Frontend checkpoints are strictly sequential: frontend checkpoint N+1 opens only after frontend audit N is FINAL_PASS.
- Phase boundaries are strict: Phase N+1 never executes before Phase N is FINAL_PASS as a whole.
- One checkpoint equals one clean scope. Do not pre-build later checkpoints.
- Done requires real source changes, required gates, a clean commit, and a pushed SHA.
- Audit must inspect actual source/diff/tests, not trust an engineer narrative.
- Retry only transient infrastructure failures. Deterministic failures stop with a concrete reason.
- Owner approval remains required for business-contract changes, destructive production actions, merge/deploy, and secrets.
- The Owner should not need Termius for normal checkpoint progression.
