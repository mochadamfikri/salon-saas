import { Suspense } from "react";
import type { Metadata } from "next";

import InviteAcceptClient from "@/components/invite/InviteAcceptClient";

export const metadata: Metadata = {
  title: "Accept invitation — Salon SaaS",
  description: "Accept a salon team invitation.",
};

export default function InviteAcceptPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-zinc-500">Loading…</p>}>
      <InviteAcceptClient />
    </Suspense>
  );
}
