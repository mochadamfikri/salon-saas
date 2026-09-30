/**
 * Server-rendered invitation acceptance.
 *
 * The proxy parks `?token=` server-side under a random nonce (HttpOnly
 * `salon_ic` cookie) and strips it from the URL, so the raw token never
 * reaches client code. This page consumes the nonce exactly once, accepts
 * the invitation via the BFF orchestration, and renders the outcome.
 */

import { cookies } from "next/headers";
import type { Metadata } from "next";

import InviteResultCard from "@/components/invite/InviteResultCard";
import {
  ACCESS_COOKIE,
  INVITE_CONTINUATION_COOKIE,
  REFRESH_COOKIE,
  decodeCookieValue,
} from "@/lib/auth/cookies";
import { consumeInviteContinuation } from "@/lib/auth/invite-continuation";
import { acceptInvitationOutcome } from "@/lib/auth/invitations";

export const metadata: Metadata = {
  title: "Accept invitation — Salon SaaS",
  description: "Accept a salon team invitation.",
};

export const dynamic = "force-dynamic";

export default async function InviteAcceptPage() {
  const store = await cookies();
  const nonce = decodeCookieValue(store.get(INVITE_CONTINUATION_COOKIE)?.value);
  const rawToken = nonce ? await consumeInviteContinuation(nonce) : null;

  if (!rawToken) {
    return <InviteResultCard result={{ state: "missing_token" }} />;
  }

  // The token is used once here, server-side, and never persisted.
  // allowRefresh: false — a Server Component cannot persist a rotated token
  // pair, so it must never trigger a refresh rotation (F-3). The proxy has
  // already resolved (and, if needed, rotated + persisted) the session
  // before this page renders, forwarding fresh cookies with the request.
  const outcome = await acceptInvitationOutcome(
    {
      accessToken: decodeCookieValue(store.get(ACCESS_COOKIE)?.value),
      refreshToken: decodeCookieValue(store.get(REFRESH_COOKIE)?.value),
    },
    rawToken,
    { allowRefresh: false },
  );

  return (
    <InviteResultCard
      result={{
        state: outcome.body.state,
        message: outcome.body.message,
        salonName: outcome.body.salon?.name ?? null,
        role: outcome.body.membership?.role ?? null,
      }}
    />
  );
}
