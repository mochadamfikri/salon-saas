"use client";

import { useCallback, useEffect, useState } from "react";
import type { BackendSalonCustomer } from "@/lib/auth/contracts";
import { Alert, Button, Field, TextInput } from "@/components/ui";

interface Props { salonId: string; }
interface Values { full_name: string; email: string; phone: string; notes: string; }
const empty: Values = { full_name: "", email: "", phone: "", notes: "" };

export default function CustomerRecords({ salonId }: Props) {
  const [customers, setCustomers] = useState<BackendSalonCustomer[]>([]);
  const [values, setValues] = useState<Values>(empty);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const load = useCallback(async () => {
    const response = await fetch(`/api/salons/${encodeURIComponent(salonId)}/customers`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.message ?? "Pelanggan tidak dapat dimuat.");
    setCustomers(data.customers);
  }, [salonId]);
  useEffect(() => {
    let current = true;
    void fetch(`/api/salons/${encodeURIComponent(salonId)}/customers`).then(async (response) => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.message ?? "Pelanggan tidak dapat dimuat.");
      if (current) setCustomers(data.customers);
    }).catch((reason: unknown) => { if (current) setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); });
    return () => { current = false; };
  }, [salonId]);

  function reset() { setEditingId(null); setValues(empty); setFieldErrors({}); }
  async function edit(customer: BackendSalonCustomer) {
    setError(null);
    try {
      const response = await fetch(`/api/salons/${encodeURIComponent(salonId)}/customers/${encodeURIComponent(customer.id)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.message ?? "Detail pelanggan tidak dapat dimuat.");
      customer = data.customer;
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); return; }
    setEditingId(customer.id);
    setValues({ full_name: customer.full_name, email: customer.email ?? "", phone: customer.phone ?? "", notes: customer.notes ?? "" });
    setFieldErrors({});
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setFieldErrors({});
    const payload: Record<string, unknown> = { full_name: values.full_name };
    for (const field of ["email", "phone", "notes"] as const) payload[field] = values[field] === "" ? null : values[field];
    try {
      const response = await fetch(`/api/salons/${encodeURIComponent(salonId)}/customers${editingId ? `/${encodeURIComponent(editingId)}` : ""}`, {
        method: editingId ? "PATCH" : "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) { if (data.fields) setFieldErrors(data.fields); throw new Error(data.message ?? "Pelanggan tidak dapat disimpan."); }
      reset(); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); }
    finally { setBusy(false); }
  }
  function update(field: keyof Values, value: string) { setValues((current) => ({ ...current, [field]: value })); }

  return <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
    <h1 className="text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Pelanggan</h1>
    <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Catat pelanggan salon, termasuk pelanggan walk-in.</p>
    {error && <Alert tone="error">{error}</Alert>}
    <form onSubmit={submit} className="mt-6 grid gap-4 rounded-xl bg-white p-5 shadow-sm dark:bg-zinc-900 sm:grid-cols-2" aria-label={editingId ? "Edit pelanggan" : "Tambah pelanggan"}>
      <Field id="customer-full-name" label="Nama lengkap" error={fieldErrors.full_name}><TextInput required value={values.full_name} onChange={(event) => update("full_name", event.target.value)} /></Field>
      <Field id="customer-email" label="Email" error={fieldErrors.email}><TextInput type="email" value={values.email} onChange={(event) => update("email", event.target.value)} /></Field>
      <Field id="customer-phone" label="Telepon" error={fieldErrors.phone}><TextInput type="tel" value={values.phone} onChange={(event) => update("phone", event.target.value)} /></Field>
      <Field id="customer-notes" label="Catatan" error={fieldErrors.notes}><textarea className="min-h-24 w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm dark:border-zinc-700" value={values.notes} onChange={(event) => update("notes", event.target.value)} /></Field>
      <div className="flex gap-2 sm:col-span-2"><Button type="submit" disabled={busy}>{busy ? "Menyimpan…" : editingId ? "Simpan perubahan" : "Tambah pelanggan"}</Button>{editingId && <Button type="button" className="bg-zinc-500" onClick={reset}>Batal</Button>}</div>
    </form>
    <section className="mt-8" aria-label="Daftar pelanggan">
      <h2 className="text-lg font-semibold">Daftar pelanggan</h2>
      {customers.length === 0 ? <p className="mt-3 text-sm text-zinc-600">Belum ada pelanggan.</p> : <ul className="mt-3 divide-y divide-zinc-200 rounded-xl bg-white dark:divide-zinc-800 dark:bg-zinc-900">{customers.map((customer) => <li key={customer.id} className="flex items-start justify-between gap-4 p-4">
        <div><h3 className="font-medium">{customer.full_name}</h3><p className="text-sm text-zinc-600 dark:text-zinc-400">{[customer.email, customer.phone].filter(Boolean).join(" · ") || "Tanpa email atau telepon"}</p>{customer.notes && <p className="mt-1 whitespace-pre-wrap text-sm">{customer.notes}</p>}</div>
        <Button type="button" className="mt-0 w-auto" onClick={() => void edit(customer)}>Detail / Edit</Button>
      </li>)}</ul>}
    </section>
  </div>;
}
