import type { Metadata } from "next";
import Link from "next/link";

import LogoutButton from "@/components/auth/LogoutButton";
import { getCurrentUser, getMySalons, requireUser } from "@/lib/auth/server-session";

export const metadata: Metadata = {
  title: "Customer dashboard — Salon SaaS",
  description: "Your Salon SaaS account overview.",
};

export const dynamic = "force-dynamic";

export default async function CustomerDashboardPage() {
  await requireUser("/customer/dashboard");
  // requireUser redirects when unauthenticated; the backend stays the
  // authority for identity — this data is display-only foundation.
  const user = (await getCurrentUser())!;
  const salons = (await getMySalons()) ?? [];

  return (
    <main className="min-h-screen bg-zinc-50 font-sans dark:bg-black">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Salon SaaS</p>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/salon/dashboard" className="text-zinc-600 hover:underline dark:text-zinc-300">
              Salon dashboard
            </Link>
            <LogoutButton />
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-10">
        <h1 className="text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Welcome</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400" data-testid="user-email">
          Signed in as {user.email}
        </p>

        <section className="mt-8 rounded-xl bg-white p-6 shadow-sm dark:bg-zinc-900">
          <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-100">Your salons</h2>
          {salons.length === 0 ? (
            <div className="mt-3">
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                You do not own or belong to any salon yet.
              </p>
              <Link
                href="/salon/create"
                className="mt-4 inline-flex rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
              >
                Create your salon
              </Link>
            </div>
          ) : (
            <ul className="mt-3 divide-y divide-zinc-200 dark:divide-zinc-800" data-testid="salon-list">
              {salons.map((m) => (
                <li key={m.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{m.salon.name}</p>
                    <p className="text-xs text-zinc-500">
                      {m.salon.slug} · role: {m.role} · status: {m.salon.status}
                    </p>
                  </div>
                  <Link
                    href={`/salon/dashboard?salon=${m.salon.id}`}
                    className="text-sm font-medium text-zinc-900 underline dark:text-zinc-100"
                  >
                    Open
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="mt-6 rounded-xl bg-white p-6 shadow-sm dark:bg-zinc-900">
          <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-100">Account</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-zinc-500">User ID</dt>
              <dd className="font-mono text-xs text-zinc-800 dark:text-zinc-200">{user.id}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-zinc-500">Status</dt>
              <dd className="text-zinc-800 dark:text-zinc-200">
                {user.is_active ? "Active" : "Inactive"}
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </main>
  );
}
