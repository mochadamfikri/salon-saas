import type { Metadata } from "next";
import Link from "next/link";

import LogoutButton from "@/components/auth/LogoutButton";
import { getMySalons, requireUser } from "@/lib/auth/server-session";

export const metadata: Metadata = {
  title: "Salon dashboard — Salon SaaS",
  description: "Manage your salon.",
};

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<{ salon?: string }>;
}

/**
 * Salon dashboard foundation (Phase 1).
 *
 * Membership and role come exclusively from the backend (`GET /me/salons`);
 * nothing about tenancy is decided in the browser. Operational features
 * (booking, services, POS, …) are Phase 2+ and intentionally absent.
 */
export default async function SalonDashboardPage({ searchParams }: PageProps) {
  await requireUser("/salon/dashboard");
  const memberships = (await getMySalons()) ?? [];
  const { salon: selectedId } = await searchParams;

  const selected =
    memberships.find((m) => m.salon.id === selectedId) ?? memberships[0] ?? null;

  return (
    <main className="min-h-screen bg-zinc-50 font-sans dark:bg-black">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {selected ? selected.salon.name : "Salon SaaS"}
          </p>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/customer/dashboard" className="text-zinc-600 hover:underline dark:text-zinc-300">
              Customer dashboard
            </Link>
            <Link href="/salon/create" className="text-zinc-600 hover:underline dark:text-zinc-300">
              New salon
            </Link>
            <LogoutButton />
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-10">
        <h1 className="text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Salon dashboard</h1>

        {memberships.length === 0 ? (
          <section className="mt-8 rounded-xl bg-white p-6 shadow-sm dark:bg-zinc-900">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              You are not a member of any salon yet.
            </p>
            <Link
              href="/salon/create"
              className="mt-4 inline-flex rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
            >
              Create your salon
            </Link>
          </section>
        ) : (
          <>
            {memberships.length > 1 && (
              <nav aria-label="Your salons" className="mt-6 flex flex-wrap gap-2" data-testid="salon-switcher">
                {memberships.map((m) => (
                  <Link
                    key={m.id}
                    href={`/salon/dashboard?salon=${m.salon.id}`}
                    aria-current={selected?.salon.id === m.salon.id ? "page" : undefined}
                    className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
                      selected?.salon.id === m.salon.id
                        ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                        : "border-zinc-300 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                    }`}
                  >
                    {m.salon.name}
                  </Link>
                ))}
              </nav>
            )}

            {selected && (
              <section
                className="mt-6 rounded-xl bg-white p-6 shadow-sm dark:bg-zinc-900"
                data-testid="salon-context"
              >
                <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-100">Salon context</h2>
                <dl className="mt-3 space-y-2 text-sm">
                  <div className="flex gap-2">
                    <dt className="w-24 shrink-0 text-zinc-500">Name</dt>
                    <dd className="text-zinc-800 dark:text-zinc-200">{selected.salon.name}</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-24 shrink-0 text-zinc-500">Slug</dt>
                    <dd className="font-mono text-xs text-zinc-800 dark:text-zinc-200">
                      {selected.salon.slug}
                    </dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-24 shrink-0 text-zinc-500">Your role</dt>
                    <dd className="text-zinc-800 dark:text-zinc-200" data-testid="membership-role">
                      {selected.role}
                    </dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-24 shrink-0 text-zinc-500">Status</dt>
                    <dd className="text-zinc-800 dark:text-zinc-200">{selected.salon.status}</dd>
                  </div>
                </dl>
                <p className="mt-4 text-xs text-zinc-500">
                  Role and membership are provided by the backend on every load — this page is a
                  Phase 1 foundation. Operational features arrive in Phase 2.
                </p>
              </section>
            )}
          </>
        )}
      </div>
    </main>
  );
}
