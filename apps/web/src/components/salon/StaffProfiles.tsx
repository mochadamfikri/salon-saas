"use client";

import { useCallback, useEffect, useState } from "react";
import type { BackendSalonService, BackendStaffProfile, BackendStaffServiceAssignment } from "@/lib/auth/contracts";

type Member = { id: string; role: string; status: string; user: { id: string; email: string } };
type Props = { salonId: string; membershipId: string; role: "owner" | "manager" | "staff" };
type Data = { profiles: BackendStaffProfile[]; members: Member[]; services: BackendSalonService[] };
const fields = ["display_name", "phone", "bio", "photo_url"] as const;
type Field = typeof fields[number];

export default function StaffProfiles({ salonId, membershipId, role }: Props) {
  const canManage = role === "owner" || role === "manager";
  const [data, setData] = useState<Data | null>(null);
  const [selected, setSelected] = useState("");
  const [assignments, setAssignments] = useState<BackendStaffServiceAssignment[]>([]);
  const [form, setForm] = useState<Record<Field, string>>({ display_name: "", phone: "", bio: "", photo_url: "" });
  const [newMembership, setNewMembership] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const profile = data?.profiles.find((item) => item.id === selected);
  const reload = useCallback(async () => {
    const response = await fetch(`/api/salons/${encodeURIComponent(salonId)}/staff-profiles`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.message ?? "Gagal memuat profil staf.");
    setData(result as Data);
  }, [salonId]);
  useEffect(() => {
    fetch(`/api/salons/${encodeURIComponent(salonId)}/staff-profiles`).then(async (response) => {
      const result = await response.json(); if (!response.ok) throw new Error(result.message ?? "Gagal memuat profil staf."); setData(result as Data);
    }).catch((reason: Error) => setError(reason.message));
  }, [salonId]);
  useEffect(() => {
    if (!profile) return;
    void fetch(`/api/salons/${encodeURIComponent(salonId)}/staff-profiles/${encodeURIComponent(profile.id)}/services`).then(async (response) => {
      const result = await response.json(); if (!response.ok) throw new Error(result.message ?? "Gagal memuat layanan staf."); setAssignments(result.assignments as BackendStaffServiceAssignment[]);
    }).catch((reason: Error) => setError(reason.message));
  }, [profile, salonId]);
  async function request(path: string, method: string, body?: unknown) {
    const response = await fetch(path, { method, ...(body === undefined ? {} : { headers: { "content-type": "application/json" }, body: JSON.stringify(body) }) });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.message ?? `Permintaan gagal (${response.status}).`);
    return result;
  }
  async function run(action: () => Promise<void>) { setBusy(true); setError(""); try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Terjadi kesalahan."); } finally { setBusy(false); } }
  const assignedIds = new Set(assignments.map((item) => item.salon_service_id));
  const eligibleMembers = data?.members.filter((member) => member.status === "active" && ["owner", "manager", "staff"].includes(member.role) && !data.profiles.some((item) => item.membership_id === member.id)) ?? [];
  return <section className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
    <header className="mb-6"><h1 className="text-2xl font-semibold">Profil Staf</h1><p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">Kelola profil operasional dan layanan yang dapat ditangani staf.</p></header>
    {error && <p role="alert" className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <div className="grid gap-6 lg:grid-cols-[minmax(220px,1fr)_2fr]">
      <aside className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700"><h2 className="font-semibold">Daftar staf</h2>
        {canManage && <form className="mt-4 flex gap-2" onSubmit={(event) => { event.preventDefault(); void run(async () => { await request(`/api/salons/${encodeURIComponent(salonId)}/staff-profiles`, "POST", { membership_id: newMembership }); setNewMembership(""); await reload(); }); }}>
          <select aria-label="Keanggotaan aktif" required value={newMembership} onChange={(event) => setNewMembership(event.target.value)} className="min-w-0 flex-1 rounded-md border bg-transparent p-2 text-sm"><option value="">Pilih anggota aktif</option>{eligibleMembers.map((member) => <option key={member.id} value={member.id}>{member.user.email} · {member.role}</option>)}</select><button disabled={busy || !newMembership} className="rounded-md bg-zinc-900 px-3 text-sm text-white disabled:opacity-50">Tambah</button>
        </form>}
        <ul className="mt-4 space-y-2">{data?.profiles.map((item) => { const member = data.members.find((entry) => entry.id === item.membership_id); return <li key={item.id}><button onClick={() => { setSelected(item.id); setForm({ display_name: item.display_name ?? "", phone: item.phone ?? "", bio: item.bio ?? "", photo_url: item.photo_url ?? "" }); }} className={`w-full rounded-lg border p-3 text-left ${selected === item.id ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950" : "border-zinc-200 dark:border-zinc-700"}`}><span className="block font-medium">{item.display_name || member?.user.email || "Profil staf"}</span><span className="text-xs text-zinc-500">{item.is_bookable ? "Dapat dipesan" : "Tidak dapat dipesan"}</span></button></li>; })}</ul>
      </aside>
      <div className="space-y-6">{profile ? <>
        <form className="rounded-xl border border-zinc-200 p-5 dark:border-zinc-700" onSubmit={(event) => { event.preventDefault(); void run(async () => { const payload = Object.fromEntries(fields.map((field) => [field, form[field] === "" ? null : form[field]])); await request(`/api/salons/${encodeURIComponent(salonId)}/staff-profiles/${encodeURIComponent(profile.id)}`, "PATCH", payload); await reload(); }); }}>
          <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">Detail profil</h2>{canManage && <button type="button" disabled={busy} onClick={() => void run(async () => { await request(`/api/salons/${encodeURIComponent(salonId)}/staff-profiles/${encodeURIComponent(profile.id)}`, "POST", { is_bookable: !profile.is_bookable }); await reload(); })} className="rounded-md border px-3 py-2 text-sm">{profile.is_bookable ? "Nonaktifkan pemesanan" : "Aktifkan pemesanan"}</button>}</div>
          {fields.map((field) => <label key={field} className="mb-3 block text-sm"><span className="mb-1 block capitalize">{field.replaceAll("_", " ")}</span>{field === "bio" ? <textarea maxLength={1000} value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} className="w-full rounded-md border bg-transparent p-2" /> : <input maxLength={field === "display_name" ? 200 : field === "phone" ? 20 : 512} value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} className="w-full rounded-md border bg-transparent p-2" />}</label>)}
          <p className="mb-3 text-xs text-zinc-500">Keanggotaan profil tidak dapat diubah.</p><button disabled={busy || !(canManage || profile.membership_id === membershipId)} className="rounded-md bg-indigo-600 px-4 py-2 text-sm text-white disabled:opacity-50">Simpan profil</button>
        </form>
        <section className="rounded-xl border border-zinc-200 p-5 dark:border-zinc-700"><h2 className="font-semibold">Layanan</h2><ul className="mt-3 divide-y divide-zinc-200 dark:divide-zinc-700">{data?.services.map((service) => { const assigned = assignedIds.has(service.id); return <li key={service.id} className="flex items-center justify-between gap-3 py-3 text-sm"><span>{service.name}</span>{canManage ? <button disabled={busy} onClick={() => void run(async () => { await request(`/api/salons/${encodeURIComponent(salonId)}/staff-profiles/${encodeURIComponent(profile.id)}/services/${encodeURIComponent(service.id)}`, assigned ? "DELETE" : "POST"); const response = await fetch(`/api/salons/${encodeURIComponent(salonId)}/staff-profiles/${encodeURIComponent(profile.id)}/services`); const result = await response.json(); if (!response.ok) throw new Error(result.message ?? "Gagal memperbarui layanan."); setAssignments(result.assignments); })} className="rounded-md border px-3 py-1.5">{assigned ? "Hapus penugasan" : "Tugaskan"}</button> : <span className="text-zinc-500">{assigned ? "Ditugaskan" : "—"}</span>}</li>; })}</ul></section>
      </> : <div className="rounded-xl border border-dashed border-zinc-300 p-10 text-center text-sm text-zinc-500">Pilih profil staf untuk melihat detail.</div>}</div>
    </div>
  </section>;
}
