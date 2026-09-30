"use client";

/**
 * Invitation acceptance flow.
 *
 * States handled: missing token, login required, register required,
 * checking, accepting, success, invalid, expired, revoked, already accepted,
 * email mismatch, backend-unavailable, generic error.
 *
 * The token comes from the `?token=` query param, is used exactly once in
 * the accept call, and is never persisted (no cookies, no storage).
 */

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Alert, Button, Card, FormStatus, PageShell } from "@/components/ui";
import type { InvitationState } from "@/lib/auth/contracts";
import { uiMessageFor } from "@/lib/auth/ui-messages";
import type { BackendErrorCode } from "@/lib/auth/backend";

interface AcceptResponse {
  ok: boolean;
  code?: BackendErrorCode;
  message?: string;
  state?: InvitationState;
  membership?: { id: string; role: string; status: string };
  salon?: { id: string; name: string; slug: string };
}

export default function InviteAcceptClient() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [state, setState] = useState<InvitationState>(token ? "checking" : "missing_token");
  const [message, setMessage] = useState<string | null>(null);
  const [salonName, setSalonName] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);

  const accept = useCallback(async () => {
    if (!token) {
      setState("missing_token");
      return;
    }
    setState("accepting");
    setMessage(null);
    try {
      const res = await fetch("/api/invitations/accept", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const payload = (await res.json()) as AcceptResponse;
      if (!res.ok || !payload.ok) {
        const nextState: InvitationState = payload.state ?? "error";
        setState(nextState);
        setMessage(payload.message ?? uiMessageFor(payload.code ?? "unknown_error"));
        return;
      }
      setState("success");
      setSalonName(payload.salon?.name ?? null);
      setRole(payload.membership?.role ?? null);
    } catch {
      setState("error");
      setMessage(uiMessageFor("network_error"));
    }
  }, [token]);

  useEffect(() => {
    // First verify the session: unauthenticated users get the login/register
    // continuation instead of an opaque failure.
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const me = await fetch("/api/auth/me");
        if (cancelled) return;
        if (me.status === 401) {
          setState("login_required");
          return;
        }
        if (!me.ok) {
          setState("error");
          setMessage(uiMessageFor("unknown_error"));
          return;
        }
      } catch {
        if (!cancelled) {
          setState("error");
          setMessage(uiMessageFor("network_error"));
        }
        return;
      }
      if (!cancelled) void accept();
    })();
    return () => {
      cancelled = true;
    };
  }, [token, accept]);

  const continuation = `/invite/accept?token=${encodeURIComponent(token)}`;

  return (
    <PageShell>
      <Card>
        <p className="text-sm font-medium text-zinc-500">Salon invitation</p>
        <h1 className="mt-2 text-2xl font-semibold text-zinc-950 dark:text-zinc-50">
          Join a salon team
        </h1>

        {(state === "checking" || state === "accepting") && (
          <FormStatus message={state === "checking" ? "Checking your invitation…" : "Accepting your invitation…"} />
        )}

        {state === "missing_token" && (
          <Alert tone="error">
            This invitation link is missing its token. Ask the salon owner for a fresh invite link.
          </Alert>
        )}

        {state === "login_required" && (
          <div className="mt-4">
            <Alert tone="info">
              You need to log in (or create an account) before accepting this invitation. Your
              invitation will continue right after.
            </Alert>
            <div className="mt-4 flex gap-3">
              <a
                href={`/login?next=${encodeURIComponent(continuation)}`}
                className="inline-flex flex-1 items-center justify-center rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
              >
                Log in
              </a>
              <a
                href={`/register?next=${encodeURIComponent(continuation)}`}
                className="inline-flex flex-1 items-center justify-center rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                Create account
              </a>
            </div>
          </div>
        )}

        {state === "success" && (
          <div className="mt-4">
            <Alert tone="success">
              Welcome{salonName ? ` to ${salonName}` : ""}! Your invitation was accepted
              {role ? ` — your role is ${role}` : ""}.
            </Alert>
            <Button type="button" onClick={() => (window.location.href = "/salon/dashboard")}>
              Go to salon dashboard
            </Button>
          </div>
        )}

        {(state === "invalid" ||
          state === "expired" ||
          state === "revoked" ||
          state === "already_accepted" ||
          state === "email_mismatch" ||
          state === "error") && (
          <div className="mt-4">
            <Alert tone={state === "already_accepted" ? "info" : "error"}>
              {message ?? "This invitation could not be accepted."}
            </Alert>
            {state === "email_mismatch" && (
              <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
                Log out and log back in with the email address the invitation was sent to, then
                open the invite link again.
              </p>
            )}
            <div className="mt-4">
              <a
                href="/salon/dashboard"
                className="text-sm font-medium text-zinc-900 underline dark:text-zinc-100"
              >
                Go to salon dashboard
              </a>
            </div>
          </div>
        )}
      </Card>
    </PageShell>
  );
}
