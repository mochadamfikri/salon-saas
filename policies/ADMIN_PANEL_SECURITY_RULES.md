# Admin Control Panel Security Rules

## Isolation
The orchestrator admin panel is separate from the Salon SaaS production/customer application.
It must never share customer-facing authentication or expose production credentials.

## Access
Initial deployment is Owner-only.
Preferred exposure order:
1. private network/Tailscale;
2. trusted access proxy;
3. public HTTPS only if protected by strong authentication and rate limiting.

## Authentication
- secure server-side session cookie;
- HttpOnly;
- Secure under HTTPS;
- SameSite=Lax or stricter;
- password stored only as a strong password hash;
- rate-limit login;
- session timeout;
- CSRF protection for state-changing browser actions.

## No Raw Shell
The browser may never submit arbitrary shell commands.
All actions map to predefined allowlisted control-plane operations.

## Secrets
Secrets live outside Git, e.g. `/etc/salon-orchestrator/*.env` with restrictive permissions.
Never display full secret values in the UI or logs.

## Git Operations
Panel/orchestrator may commit/push only the dedicated orchestration branch for control-plane artifacts.
Engineering workers push only their assigned feature branches.
No merge or force-push from routine panel controls.

## File Upload
Phase uploads:
- size-limited;
- Markdown/YAML/approved ZIP only;
- reject executable binaries;
- reject symlinks;
- reject absolute paths and `..` traversal;
- extract into a temporary isolated directory;
- preview before activation.

## Logging
- redact tokens/credentials;
- log control actions and actor;
- record worker state transitions;
- retain audit trail for phase activation, retries, pauses, and Owner decisions.

## Dangerous Actions
Any future action involving deploy, production restart, migration execution, or destructive DB operation must be outside routine worker controls and require explicit Owner confirmation plus separate policy approval.
