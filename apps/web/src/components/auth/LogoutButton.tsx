"use client";

/**
 * Logout button. Calls the BFF logout (backend revocation + cookie expiry),
 * then navigates to the login page. Protected pages become inaccessible
 * because the session cookies are gone.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LogoutButton({ className = "" }: { className?: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function onClick() {
    setPending(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Session cookies are expired server-side regardless.
    } finally {
      router.push("/login");
      router.refresh();
      setPending(false);
    }
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      data-testid="logout-button"
      className={
        "inline-flex items-center rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium " +
        "text-zinc-700 hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-200 " +
        "dark:hover:bg-zinc-800 " +
        className
      }
    >
      {pending ? "Logging out…" : "Log out"}
    </button>
  );
}
