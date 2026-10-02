import Link from "next/link";
import { cookies } from "next/headers";

import { checkApiConnectivity } from "@/lib/api";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth/cookies";

export const dynamic = "force-dynamic";

const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

export default async function Home() {
  const connectivity = await checkApiConnectivity(apiBaseUrl);
  const store = await cookies();
  const signedIn = Boolean(
    store.get(ACCESS_COOKIE)?.value ?? store.get(REFRESH_COOKIE)?.value,
  );

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 p-8 font-sans dark:bg-black">
      <section className="w-full max-w-xl rounded-xl bg-white p-8 shadow-sm dark:bg-zinc-900">
        <p className="text-sm font-medium text-zinc-500">Salon SaaS Platform</p>
        <h1 className="mt-2 text-3xl font-semibold text-zinc-950 dark:text-zinc-50">
          Beauty salon management, simplified
        </h1>
        <p className="mt-4 text-zinc-600 dark:text-zinc-300">
          Online booking, staff management, and salon operations — all in one place.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          {signedIn ? (
            <>
              <Link
                href="/customer/dashboard"
                className="inline-flex rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
              >
                Customer dashboard
              </Link>
              <Link
                href="/salon/dashboard"
                className="inline-flex rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                Salon dashboard
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="inline-flex rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
              >
                Log in
              </Link>
              <Link
                href="/register"
                className="inline-flex rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                Create account
              </Link>
            </>
          )}
        </div>

        <p
          className="mt-6 rounded-md bg-zinc-100 px-4 py-3 font-mono text-sm text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"
          data-testid="api-connectivity"
        >
          API connectivity: {connectivity.status}
          {connectivity.status === "unavailable" ? ` (${connectivity.message})` : ""}
        </p>
      </section>
    </main>
  );
}
