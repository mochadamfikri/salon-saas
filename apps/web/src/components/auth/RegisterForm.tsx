"use client";

/**
 * Registration form. Enforces the backend password policy client-side for UX
 * (12..128 chars, unicode-safe, no arbitrary complexity rules); the backend
 * remains authoritative.
 */

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Alert, Button, Card, Field, FormStatus, PageShell, TextInput } from "@/components/ui";
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  safeRedirectPath,
  validateEmail,
  validatePassword,
} from "@/lib/auth/validation";

interface RegisterResponse {
  ok: boolean;
  code?: string;
  message?: string;
  field?: string;
  user?: { id: string; email: string };
}

export default function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string; confirm?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);

    const errors: { email?: string; password?: string; confirm?: string } = {};
    const emailCheck = validateEmail(email.trim());
    if (!emailCheck.valid) errors.email = emailCheck.error;
    const passwordCheck = validatePassword(password);
    if (!passwordCheck.valid) errors.password = passwordCheck.error;
    if (!errors.password && confirm !== password) {
      errors.confirm = "Passwords do not match.";
    }
    setFieldErrors(errors);
    if (errors.email ?? errors.password ?? errors.confirm) return;

    setPending(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const payload = (await res.json()) as RegisterResponse;
      if (!res.ok || !payload.ok) {
        if (payload.field === "email" || payload.field === "password") {
          setFieldErrors({ [payload.field]: payload.message ?? "Invalid value." });
        } else {
          setFormError(payload.message ?? "Registration failed. Please try again.");
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
        <h1 className="mt-2 text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Create your account</h1>
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
          <Field
            id="password"
            label="Password"
            error={fieldErrors.password}
            hint={`At least ${PASSWORD_MIN_LENGTH} characters (up to ${PASSWORD_MAX_LENGTH}). Any characters are fine — no forced symbols or capitals.`}
          >
            <TextInput
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              data-testid="password-input"
            />
          </Field>
          <Field id="confirm" label="Confirm password" error={fieldErrors.confirm}>
            <TextInput
              id="confirm"
              name="confirm"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              data-testid="confirm-input"
            />
          </Field>
          {formError && <Alert tone="error">{formError}</Alert>}
          <Button type="submit" loading={pending} data-testid="register-submit">
            Create account
          </Button>
          <FormStatus message={pending ? "Creating your account…" : null} />
        </form>
        <p className="mt-6 text-center text-sm text-zinc-600 dark:text-zinc-400">
          Already have an account?{" "}
          <a href="/login" className="font-medium text-zinc-900 underline dark:text-zinc-100">
            Log in
          </a>
        </p>
      </Card>
    </PageShell>
  );
}
