import { Suspense } from "react";
import type { Metadata } from "next";

import LoginForm from "@/components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Log in — Salon SaaS",
  description: "Log in to your Salon SaaS account.",
};

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-zinc-500">Loading…</p>}>
      <LoginForm />
    </Suspense>
  );
}
