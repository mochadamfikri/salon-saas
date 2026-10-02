"use client";

import { useCallback, useEffect, useState } from "react";
import type { BackendSalonService, TenantRole } from "@/lib/auth/contracts";
import { Alert, Button, Field, TextInput } from "@/components/ui";

interface Props { salonId: string; role: TenantRole; }
interface Values { name: string; description: string; category: string; duration_minutes: string; price_amount: string; currency: string; }
const emptyValues: Values = { name: "", description: "", category: "", duration_minutes: "", price_amount: "", currency: "IDR" };
const mutationRoles: TenantRole[] = ["owner", "manager"];

export default function ServiceCatalog({ salonId, role }: Props) {
  const canMutate = mutationRoles.includes(role);
  const [services, setServices] = useState<BackendSalonService[]>([]);
  const [values, setValues] = useState<Values>(emptyValues);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [clearDescription, setClearDescription] = useState(false);
  const [clearCategory, setClearCategory] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch(`/api/salons/${encodeURIComponent(salonId)}/services`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.message ?? "Layanan tidak dapat dimuat.");
    setServices(data.services);
  }, [salonId]);

  useEffect(() => {
    let current = true;
    void fetch(`/api/salons/${encodeURIComponent(salonId)}/services`)
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.message ?? "Layanan tidak dapat dimuat.");
        if (current) setServices(data.services);
      })
      .catch((reason: unknown) => { if (current) setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); });
    return () => { current = false; };
  }, [salonId]);

  function beginEdit(service: BackendSalonService) {
    setEditingId(service.id);
    setClearDescription(false);
    setClearCategory(false);
    setValues({ name: service.name, description: service.description ?? "", category: service.category ?? "", duration_minutes: String(service.duration_minutes), price_amount: service.price_amount, currency: service.currency });
    setFieldErrors({});
  }

  function clearForm() { setEditingId(null); setValues(emptyValues); setFieldErrors({}); setClearDescription(false); setClearCategory(false); }
  function update(field: keyof Values, value: string) { setValues((current) => ({ ...current, [field]: value })); }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(null); setFieldErrors({});
    const payload: Record<string, unknown> = {
      name: values.name,
      duration_minutes: Number(values.duration_minutes),
      price_amount: values.price_amount,
      currency: values.currency,
      description: clearDescription ? null : values.description,
      category: clearCategory ? null : values.category,
    };
    const url = `/api/salons/${encodeURIComponent(salonId)}/services${editingId ? `/${encodeURIComponent(editingId)}` : ""}`;
    try {
      const response = await fetch(url, { method: editingId ? "PATCH" : "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok) {
        if (data.fields) setFieldErrors(data.fields);
        throw new Error(data.message ?? "Layanan tidak dapat disimpan.");
      }
      clearForm();
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); }
    finally { setBusy(false); }
  }

  async function toggleActive(service: BackendSalonService) {
    setBusy(true); setError(null);
    try {
      const action = service.is_active ? "deactivate" : "activate";
      const response = await fetch(`/api/salons/${encodeURIComponent(salonId)}/services/${encodeURIComponent(service.id)}/${action}`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message ?? "Status layanan tidak dapat diubah.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); }
    finally { setBusy(false); }
  }

  return <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
    <h1 className="text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Katalog Layanan</h1>
    <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Kelola layanan salon dan harga.</p>
    {error && <Alert tone="error">{error}</Alert>}
    {canMutate && <form onSubmit={submit} className="mt-6 grid gap-4 rounded-xl bg-white p-5 shadow-sm dark:bg-zinc-900 sm:grid-cols-2" aria-label={editingId ? "Edit layanan" : "Tambah layanan"}>
      <Field id="service-name" label="Nama layanan" error={fieldErrors.name}><TextInput id="service-name" required maxLength={200} value={values.name} onChange={(event) => update("name", event.target.value)} /></Field>
      <Field id="service-category" label="Kategori (opsional)"><TextInput id="service-category" maxLength={100} value={values.category} disabled={clearCategory} onChange={(event) => update("category", event.target.value)} />{editingId && <label className="mt-2 flex items-center gap-2 text-xs text-zinc-600"><input type="checkbox" checked={clearCategory} onChange={(event) => setClearCategory(event.target.checked)} />Hapus kategori (kirim null)</label>}</Field>
      <Field id="service-description" label="Deskripsi (opsional)"><TextInput id="service-description" maxLength={1000} value={values.description} disabled={clearDescription} onChange={(event) => update("description", event.target.value)} />{editingId && <label className="mt-2 flex items-center gap-2 text-xs text-zinc-600"><input type="checkbox" checked={clearDescription} onChange={(event) => setClearDescription(event.target.checked)} />Hapus deskripsi (kirim null)</label>}</Field>
      <Field id="service-duration" label="Durasi (menit)" error={fieldErrors.duration_minutes}><TextInput id="service-duration" type="number" min={1} step={1} required value={values.duration_minutes} onChange={(event) => update("duration_minutes", event.target.value)} /></Field>
      <Field id="service-price" label="Harga" hint="Masukkan nominal desimal, maksimal 2 angka di belakang koma." error={fieldErrors.price_amount}><TextInput id="service-price" inputMode="decimal" required value={values.price_amount} onChange={(event) => update("price_amount", event.target.value)} /></Field>
      <Field id="service-currency" label="Mata uang" error={fieldErrors.currency}><TextInput id="service-currency" required minLength={3} maxLength={3} value={values.currency} onChange={(event) => update("currency", event.target.value.toUpperCase())} /></Field>
      <div className="flex gap-3 sm:col-span-2"><Button type="submit" loading={busy}>{editingId ? "Simpan perubahan" : "Tambah layanan"}</Button>{editingId && <button type="button" className="mt-6 rounded-md border px-4 py-2 text-sm" onClick={clearForm}>Batal</button>}</div>
    </form>}
    <section className="mt-6 overflow-hidden rounded-xl bg-white shadow-sm dark:bg-zinc-900" aria-label="Daftar layanan">
      {services.length === 0 ? <p className="p-5 text-sm text-zinc-600 dark:text-zinc-400">Belum ada layanan.</p> : <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">{services.map((service) => <li key={service.id} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between" data-testid="service-item">
        <div><div className="flex flex-wrap items-center gap-2"><h2 className="font-medium text-zinc-900 dark:text-zinc-100">{service.name}</h2><span className={`rounded-full px-2 py-0.5 text-xs ${service.is_active ? "bg-green-100 text-green-800" : "bg-zinc-100 text-zinc-700"}`} data-testid="service-status">{service.is_active ? "Aktif" : "Nonaktif"}</span></div>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{service.duration_minutes} menit · {service.currency} {service.price_amount}</p>
          {service.category && <p className="text-xs text-zinc-500">{service.category}</p>}{service.description && <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{service.description}</p>}
        </div>
        {canMutate && <div className="flex gap-2"><button type="button" className="rounded-md border px-3 py-2 text-sm" onClick={() => beginEdit(service)}>Edit</button><button type="button" className="rounded-md border px-3 py-2 text-sm" disabled={busy} onClick={() => toggleActive(service)}>{service.is_active ? "Nonaktifkan" : "Aktifkan"}</button></div>}
      </li>)}</ul>}
    </section>
  </div>;
}
