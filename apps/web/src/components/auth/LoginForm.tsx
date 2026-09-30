"use client";

/**
 * Login form. Talks only to the BFF (/api/auth/login) — credentials go to
 * our own server, tokens never touch the browser.
 */

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Alert, Button, Card, Field, FormStatus, PageShell, TextInput } from "@/components/ui";
import { safeRedirectPath, validateEmail } from "@/lib/auth/validation";

interface LoginResponse {
  ok: boolean;
  code?: string;
  message?: string;
  field?: string;
  user?: { id: string; email: string };
}

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);

    const errors: { email?: string; password?: string } = {};
    const emailCheck = validateEmail(email.trim());
    if (!emailCheck.valid) errors.email = emailCheck.error;
    if (!password) errors.password = "Password is required.";
    setFieldErrors(errors);
    if (errors.email ?? errors.password) return;

    setPending(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const payload = (await res.json()) as LoginResponse;
      if (!res.ok || !payload.ok) {
        if (payload.field === "email" || payload.field === "password") {
          setFieldErrors({ [payload.field]: payload.message ?? "Invalid value." });
        } else {
          // Generic message from the BFF — no user enumeration.
          setFormError(payload.message ?? "Invalid email or password.");
        }
        return;
      }
      const dest = safeRedirectPath(searchParams.get("next"), "/customer/dashboard");
      router.push(dest);
      router.refresh();
    } catch {
      setFormError("Could not reach the server. Check your connection and try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <PageShell>
      <Card>
        <p className="text-sm font-medium text-zinc-500">Salon SaaS Platform</p>
        <h1 className="mt-2 text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Log in</h1>
        <form onSubmit={onSubmit} noValidate className="mt-6">
          <Field id="email" label="Email" error={fieldErrors.email}>
            <TextInput
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="email-input"
            />
          </Field>
          <Field id="password" label="Password" error={fieldErrors.password}>
            <TextInput
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              data-testid="password-input"
            />
          </Field>
          {formError && <Alert tone="error">{formError}</Alert>}
          <Button type="submit" loading={pending} data-testid="login-submit">
            Log in
          </Button>
          <FormStatus message={pending ? "Signing you in…" : null} />
        </form>
        <p className="mt-6 text-center text-sm text-zinc-600 dark:text-zinc-400">
          No account yet?{" "}
          <a href="/register" className="font-medium text-zinc-900 underline dark:text-zinc-100">
            Create one
          </a>
        </p>
      </Card>
    </PageShell>
  );
}
