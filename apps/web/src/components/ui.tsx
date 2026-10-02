/**
 * Minimal UI primitives (Tailwind). Accessible by default:
 * labels are always rendered, errors use aria-describedby + role=alert.
 */

import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`w-full max-w-md rounded-xl bg-white p-8 shadow-sm dark:bg-zinc-900 ${className}`}>
      {children}
    </section>
  );
}

export function PageShell({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 p-8 font-sans dark:bg-black">
      {children}
    </main>
  );
}

interface FieldProps {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}

export function Field({ id, label, error, hint, children }: FieldProps) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="mt-4 first:mt-0">
      <label htmlFor={id} className="block text-sm font-medium text-zinc-700 dark:text-zinc-200">
        {label}
      </label>
      <div aria-describedby={describedBy}>{children}</div>
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-zinc-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1 text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}

const inputClass =
  "mt-1 block w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm " +
  "focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 " +
  "disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100";

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${inputClass} ${props.className ?? ""}`} />;
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
}

export function Button({ loading, children, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      disabled={props.disabled ?? loading}
      className={
        "mt-6 inline-flex w-full items-center justify-center rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white " +
        "hover:bg-zinc-700 focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 " +
        "disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300 " +
        (props.className ?? "")
      }
    >
      {loading ? "Please wait…" : children}
    </button>
  );
}

export function Alert({ tone, children }: { tone: "error" | "info" | "success"; children: ReactNode }) {
  const tones = {
    error: "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200",
    info: "border-zinc-200 bg-zinc-100 text-zinc-800 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200",
    success:
      "border-green-200 bg-green-50 text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200",
  } as const;
  return (
    <div role="alert" className={`mt-4 rounded-md border px-4 py-3 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

export function FormStatus({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p aria-live="polite" className="mt-2 text-xs text-zinc-500" data-testid="form-status">
      {message}
    </p>
  );
}
