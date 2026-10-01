"use client";

import { useCallback, useEffect, useState } from "react";
import type { BackendStaffAvailability, BackendStaffProfile } from "@/lib/auth/contracts";

type Props = { salonId: string; membershipId: string; role: "owner" | "manager" | "staff"; userId: string };
type Form = { day_of_week: number; start_time: string; end_time: string };
const weekdays = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];
const empty: Form = { day_of_week: 0, start_time: "09:00", end_time: "17:00" };

export default function StaffAvailability({ salonId, membershipId, role }: Props) {
  const canManageAny = role === "owner" || role === "manager";
  const [profiles, setProfiles] = useState<BackendStaffProfile[]>([]);
  const [selected, setSelected] = useState("");
  const [slots, setSlots] = useState<BackendStaffAvailability[]>([]);
  const [editing, setEditing] = useState("");
  const [form, setForm] = useState<Form>(empty);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const profile = profiles.find((item) => item.id === selected);
  const canEdit = canManageAny || profile?.membership_id === membershipId;
  const base = `/api/salons/${encodeURIComponent(salonId)}/staff-profiles`;
  const loadSlots = useCallback(async (profileId: string) => {
    const response = await fetch(`${base}/${encodeURIComponent(profileId)}/availability`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.message ?? "Gagal memuat jadwal.");
    setSlots(result.availability as BackendStaffAvailability[]);
  }, [base]);
  useEffect(() => {
    fetch(base).then(async (response) => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Gagal memuat profil staf.");
      const own = (result.profiles as BackendStaffProfile[]).find((item) => item.membership_id === membershipId);
      const options = canManageAny ? result.profiles as BackendStaffProfile[] : own ? [own] : [];
      setProfiles(options);
      setSelected(own?.id ?? options[0]?.id ?? "");
    }).catch((reason: Error) => setError(reason.message));
  }, [base, canManageAny, membershipId]);
  useEffect(() => {
    if (!selected) { setSlots([]); return; }
    loadSlots(selected).catch((reason: Error) => setError(reason.message));
  }, [loadSlots, selected]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || form.start_time >= form.end_time) { setError("Waktu mulai harus sebelum waktu selesai."); return; }
    setBusy(true); setError("");
    try {
      const response = await fetch(`${base}/${encodeURIComponent(selected)}/availability${editing ? `/${encodeURIComponent(editing)}` : ""}`, {
        method: editing ? "PATCH" : "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(form),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(response.status === 409 ? "Jadwal bertabrakan dengan slot lain. Slot yang bersebelahan diperbolehkan." : result.message ?? "Gagal menyimpan jadwal.");
      setEditing(""); setForm(empty); await loadSlots(selected);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); }
    finally { setBusy(false); }
  }
  async function remove(id: string) {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`${base}/${encodeURIComponent(selected)}/availability/${encodeURIComponent(id)}`, { method: "DELETE" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.message ?? "Gagal menghapus jadwal.");
      await loadSlots(selected);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); }
    finally { setBusy(false); }
  }
  return <section className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
    <header className="mb-6"><h1 className="text-2xl font-semibold">Ketersediaan Staf Mingguan</h1><p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">Atur jam ketersediaan per hari. Slot bersebelahan diperbolehkan.</p></header>
    {error && <p role="alert" className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {canManageAny && <label className="mb-5 block text-sm font-medium">Profil staf<select className="mt-1 block w-full rounded-md border border-zinc-300 bg-white p-2 dark:bg-zinc-900" value={selected} onChange={(event) => { setSelected(event.target.value); setEditing(""); setForm(empty); }}><option value="">Pilih profil</option>{profiles.map((item) => <option key={item.id} value={item.id}>{item.display_name || item.membership_id}</option>)}</select></label>}
    {selected ? <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="space-y-3">{weekdays.map((day, dayIndex) => <section key={day} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"><h2 className="font-semibold">{day}</h2><div className="mt-2 space-y-2">{slots.filter((slot) => slot.day_of_week === dayIndex).map((slot) => <div key={slot.id} className="flex flex-wrap items-center justify-between gap-2 text-sm"><span>{slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)}{!slot.is_available && " · Tidak tersedia"}</span>{canEdit && <span className="flex gap-2"><button type="button" disabled={busy} className="underline" onClick={() => { setEditing(slot.id); setForm({ day_of_week: slot.day_of_week, start_time: slot.start_time.slice(0, 5), end_time: slot.end_time.slice(0, 5) }); }}>Ubah</button><button type="button" disabled={busy} className="text-red-700 underline" onClick={() => void remove(slot.id)}>Hapus</button></span>}</div>)}{slots.every((slot) => slot.day_of_week !== dayIndex) && <p className="text-sm text-zinc-500">Belum ada jadwal</p>}</div></section>)}</div>
      {canEdit && <form onSubmit={submit} className="h-fit space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"><h2 className="font-semibold">{editing ? "Ubah slot" : "Tambah slot"}</h2><label className="block text-sm">Hari<select className="mt-1 block w-full rounded border p-2 dark:bg-zinc-900" value={form.day_of_week} onChange={(event) => setForm({ ...form, day_of_week: Number(event.target.value) })}>{weekdays.map((day, index) => <option key={day} value={index}>{day}</option>)}</select></label><label className="block text-sm">Mulai<input required type="time" className="mt-1 block w-full rounded border p-2 dark:bg-zinc-900" value={form.start_time} onChange={(event) => setForm({ ...form, start_time: event.target.value })} /></label><label className="block text-sm">Selesai<input required type="time" className="mt-1 block w-full rounded border p-2 dark:bg-zinc-900" value={form.end_time} onChange={(event) => setForm({ ...form, end_time: event.target.value })} /></label>{form.start_time >= form.end_time && <p className="text-sm text-red-700">Waktu mulai harus sebelum waktu selesai.</p>}<button disabled={busy || form.start_time >= form.end_time} className="w-full rounded bg-zinc-900 px-3 py-2 text-sm text-white disabled:opacity-50">{busy ? "Menyimpan…" : editing ? "Simpan perubahan" : "Tambah slot"}</button>{editing && <button type="button" className="w-full rounded border px-3 py-2 text-sm" onClick={() => { setEditing(""); setForm(empty); }}>Batal</button>}</form>}
    </div> : <p>Belum ada profil staf yang tersedia.</p>}
  </section>;
}
