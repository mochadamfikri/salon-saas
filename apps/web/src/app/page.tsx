import { checkApiConnectivity } from "@/lib/api";

export const dynamic = "force-dynamic";

const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

export default async function Home() {
  const connectivity = await checkApiConnectivity(apiBaseUrl);

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 p-8 font-sans dark:bg-black">
      <section className="w-full max-w-xl rounded-xl bg-white p-8 shadow-sm dark:bg-zinc-900">
        <p className="text-sm font-medium text-zinc-500">Salon SaaS Platform</p>
        <h1 className="mt-2 text-3xl font-semibold text-zinc-950 dark:text-zinc-50">
          Phase 0 engineering foundation
        </h1>
        <p className="mt-4 text-zinc-600 dark:text-zinc-300">
          This development indicator verifies configured frontend-to-backend connectivity only.
        </p>
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
