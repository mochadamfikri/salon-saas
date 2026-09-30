import { Suspense } from "react";
import type { Metadata } from "next";

import RegisterForm from "@/components/auth/RegisterForm";

export const metadata: Metadata = {
  title: "Create account — Salon SaaS",
  description: "Create your Salon SaaS account.",
};

export default function RegisterPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-zinc-500">Loading…</p>}>
      <RegisterForm />
    </Suspense>
  );
}
