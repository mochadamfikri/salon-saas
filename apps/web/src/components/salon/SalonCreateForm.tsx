"use client";

/**
 * Salon creation form (authenticated only — the page guards this).
 *
 * The slug is OPTIONAL: when left blank, only { name } is sent and the
 * backend auto-generates the slug. An explicit slug is validated for UX,
 * but the backend decides slug validity, reserved slugs, uniqueness, and
 * OWNER provisioning. The UI never assumes ownership from local state —
 * only the backend response grants it.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Alert, Button, Card, Field, FormStatus, PageShell, TextInput } from "@/components/ui";
import { suggestSlug, validateOptionalSlug, validateSalonName } from "@/lib/auth/validation";

interface CreateSalonResponse {
  ok: boolean;
  code?: string;
  message?: string;
  field?: string;
  salon?: { id: string; name: string; slug: string; status: string };
}

export default function SalonCreateForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ name?: string; slug?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function onNameChange(value: string) {
    setName(value);
    if (!slugTouched) setSlug(suggestSlug(value));
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);

    const errors: { name?: string; slug?: string } = {};
    const nameCheck = validateSalonName(name);
    if (!nameCheck.valid) errors.name = nameCheck.error;
    // Blank slug is allowed (backend auto-generates); an explicit slug is validated.
    const trimmedSlug = slug.trim().toLowerCase();
    const slugCheck = validateOptionalSlug(trimmedSlug);
    if (!slugCheck.valid) errors.slug = slugCheck.error;
    setFieldErrors(errors);
    if (errors.name ?? errors.slug) return;

    setPending(true);
    try {
      const res = await fetch("/api/salons", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(
          trimmedSlug ? { name: name.trim(), slug: trimmedSlug } : { name: name.trim() },
        ),
      });
      const payload = (await res.json()) as CreateSalonResponse;
      if (!res.ok || !payload.ok) {
        if (payload.field === "name" || payload.field === "slug") {
          setFieldErrors({ [payload.field]: payload.message ?? "Invalid value." });
        } else {
          setFormError(payload.message ?? "Could not create the salon. Please try again.");
        }
        return;
      }
      // Backend confirmed creation (+ OWNER membership) — go salon-side.
      router.push("/salon/dashboard");
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
        <h1 className="mt-2 text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Create your salon</h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          You will become the owner of this salon.
        </p>
        <form onSubmit={onSubmit} noValidate className="mt-6">
          <Field id="name" label="Salon name" error={fieldErrors.name}>
            <TextInput
              id="name"
              name="name"
              type="text"
              autoComplete="organization"
              required
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              data-testid="salon-name-input"
            />
          </Field>
          <Field
            id="slug"
            label="Salon URL slug (optional)"
            error={fieldErrors.slug}
            hint="Lowercase letters, numbers, and hyphens only. Leave blank and we'll generate one for you."
          >
            <TextInput
              id="slug"
              name="slug"
              type="text"
              autoComplete="off"
              value={slug}
              onChange={(e) => {
                setSlugTouched(true);
                setSlug(e.target.value);
              }}
              data-testid="salon-slug-input"
            />
          </Field>
          {formError && <Alert tone="error">{formError}</Alert>}
          <Button type="submit" loading={pending} data-testid="salon-create-submit">
            Create salon
          </Button>
          <FormStatus message={pending ? "Creating your salon…" : null} />
        </form>
      </Card>
    </PageShell>
  );
}
