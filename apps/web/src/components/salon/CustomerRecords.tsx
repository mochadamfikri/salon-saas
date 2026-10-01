"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { BackendSalonCustomer, TenantRole } from "@/lib/auth/contracts";

type Values = { full_name: string; email: string; phone: string; notes: string };
const empty: Values = { full_name: "", email: "", phone: "", notes: "" };

export default function CustomerRecords({ salonId, role }: { salonId: string; role: TenantRole }) {
  const [customers, setCustomers] = useState<BackendSalonCustomer[]>([]);
  const [selected, setSelected] = useState<BackendSalonCustomer | null>(null);
  const [values, setValues] = useState<Values>(empty);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const canEdit = role === "owner" || role === "manager" || role === "staff";
  const endpoint = `/api/salons/${encodeURIComponent(salonId)}/customers`;

  const refresh = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const response = await fetch(endpoint); const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Daftar pelanggan tidak dapat dimuat.");
      setCustomers(result.customers);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); }
    finally { setLoading(false); }
  }, [endpoint]);
  useEffect(() => { const timer = window.setTimeout(() => { void refresh(); }, 0); return () => window.clearTimeout(timer); }, [refresh]);

  function startCreate() { setSelected(null); setValues(empty); setError(""); }
  async function selectCustomer(customer: BackendSalonCustomer) {
    setError("");
    try {
      const response = await fetch(`${endpoint}/${encodeURIComponent(customer.id)}`); const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Detail pelanggan tidak dapat dimuat.");
      const detail: BackendSalonCustomer = result.customer; setSelected(detail);
      setValues({ full_name: detail.full_name, email: detail.email ?? "", phone: detail.phone ?? "", notes: detail.notes ?? "" });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const nullable = (value: string) => value.trim() || null;
    const payload = { full_name: values.full_name.trim(), email: nullable(values.email), phone: nullable(values.phone), notes: nullable(values.notes) };
    try {
      const response = await fetch(selected ? `${endpoint}/${encodeURIComponent(selected.id)}` : endpoint, {
        method: selected ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Data pelanggan tidak dapat disimpan.");
      await refresh();
      if (selected) await selectCustomer(result.customer);
      else { setSelected(result.customer); setValues({ full_name: result.customer.full_name, email: result.customer.email ?? "", phone: result.customer.phone ?? "", notes: result.customer.notes ?? "" }); }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); }
    finally { setBusy(false); }
  }

  return <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">Pelanggan</h1><p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Kelola catatan pelanggan salon.</p></div>
      {canEdit && <button type="button" className="rounded-md bg-zinc-900 px-4 py-2 text-sm text-white dark:bg-zinc-100 dark:text-zinc-900" onClick={startCreate}>Tambah pelanggan</button>}</div>
    {error && <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <section className="overflow-hidden rounded-xl bg-white shadow-sm dark:bg-zinc-900" aria-label="Daftar pelanggan">
        {loading ? <p className="p-5 text-sm">Memuat pelanggan…</p> : customers.length === 0 ? <p className="p-5 text-sm text-zinc-600 dark:text-zinc-400">Belum ada pelanggan.</p> : <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">{customers.map((customer) => <li key={customer.id}><button type="button" className="w-full p-4 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800" onClick={() => void selectCustomer(customer)}><span className="block font-medium">{customer.full_name}</span><span className="mt-1 block text-sm text-zinc-600 dark:text-zinc-400">{customer.phone || customer.email || "Tanpa kontak"}</span></button></li>)}</ul>}
      </section>
      {canEdit && <section className="rounded-xl bg-white p-5 shadow-sm dark:bg-zinc-900" aria-label={selected ? "Detail pelanggan" : "Form pelanggan"}>
        <h2 className="text-lg font-medium">{selected ? "Detail pelanggan" : "Pelanggan baru"}</h2>
        <form className="mt-4 space-y-4" onSubmit={submit}>
          <label className="block text-sm">Nama lengkap *<input required maxLength={200} className="mt-1 w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700" value={values.full_name} onChange={(event) => setValues({ ...values, full_name: event.target.value })} /></label>
          <label className="block text-sm">Email<input type="email" maxLength={320} className="mt-1 w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700" value={values.email} onChange={(event) => setValues({ ...values, email: event.target.value })} /></label>
          <label className="block text-sm">Telepon<input maxLength={20} className="mt-1 w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700" value={values.phone} onChange={(event) => setValues({ ...values, phone: event.target.value })} /></label>
          <label className="block text-sm">Catatan<textarea maxLength={1000} rows={3} className="mt-1 w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700" value={values.notes} onChange={(event) => setValues({ ...values, notes: event.target.value })} /></label>
          <p className="text-xs text-zinc-500">Email, telepon, dan catatan dapat dikosongkan. Pelanggan tanpa kontak tetap dapat dibuat.</p>
          <button disabled={busy} className="rounded-md bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900">{busy ? "Menyimpan…" : selected ? "Simpan perubahan" : "Tambah pelanggan"}</button>
        </form>
      </section>}
    </div>
  </main>;
}
