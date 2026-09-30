/**
 * Server-rendered invitation result.
 *
 * The raw invitation token never reaches this component: the page consumes
 * the server-side continuation nonce and performs the accept server-side,
 * then renders only the outcome state here.
 */

import Link from "next/link";

import { Alert, Card, PageShell } from "@/components/ui";
import type { InvitationState } from "@/lib/auth/contracts";

export interface InvitePageResult {
  state: InvitationState | "missing_token";
  message?: string;
  salonName?: string | null;
  role?: string | null;
}

function DashboardLink() {
  return (
    <Link
      href="/salon/dashboard"
      className="mt-4 inline-flex rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
    >
      Go to salon dashboard
    </Link>
  );
}

export default function InviteResultCard({ result }: { result: InvitePageResult }) {
  const { state } = result;

  return (
    <PageShell>
      <Card>
        <p className="text-sm font-medium text-zinc-500">Salon invitation</p>
        <h1 className="mt-2 text-2xl font-semibold text-zinc-950 dark:text-zinc-50">
          Join a salon team
        </h1>

        {state === "success" && (
          <div className="mt-4" data-testid="invite-success">
            <Alert tone="success">
              Welcome{result.salonName ? ` to ${result.salonName}` : ""}! Your invitation was
              accepted{result.role ? ` — your role is ${result.role}` : ""}.
            </Alert>
            <DashboardLink />
          </div>
        )}

        {state === "already_accepted" && (
          <div className="mt-4" data-testid="invite-already-accepted">
            <Alert tone="info">{result.message ?? "This invitation was already accepted."}</Alert>
            <DashboardLink />
          </div>
        )}

        {state === "login_required" && (
          <div className="mt-4" data-testid="invite-login-required">
            <Alert tone="info">
              {result.message ?? "Please log in to accept this invitation."} Your invitation is
              held securely and will continue right after.
            </Alert>
            <div className="mt-4 flex gap-3">
              <Link
                href="/login?next=/invite/accept"
                className="inline-flex flex-1 items-center justify-center rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
              >
                Log in
              </Link>
              <Link
                href="/register?next=/invite/accept"
                className="inline-flex flex-1 items-center justify-center rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                Create account
              </Link>
            </div>
          </div>
        )}

        {state === "missing_token" && (
          <div className="mt-4" data-testid="invite-missing-token">
            <Alert tone="error">
              This invitation link is missing its token, or it was already used. Ask the salon
              owner for a fresh invite link.
            </Alert>
            <DashboardLink />
          </div>
        )}

        {(state === "invalid" ||
          state === "expired" ||
          state === "revoked" ||
          state === "email_mismatch" ||
          state === "error" ||
          state === "checking" ||
          state === "accepting") && (
          <div className="mt-4" data-testid={`invite-${state}`}>
            <Alert tone="error">
              {result.message ?? "This invitation could not be accepted."}
            </Alert>
            {state === "email_mismatch" && (
              <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
                Log out and log back in with the email address the invitation was sent to, then
                open the invite link again.
              </p>
            )}
            <DashboardLink />
          </div>
        )}
      </Card>
    </PageShell>
  );
}
