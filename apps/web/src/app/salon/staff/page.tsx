import type { Metadata } from "next";
import StaffProfiles from "@/components/salon/StaffProfiles";
import { getMySalons, requireUser } from "@/lib/auth/server-session";
export const metadata: Metadata = { title: "Profil Staf — Salon SaaS" };
export const dynamic = "force-dynamic";
type Props = { searchParams: Promise<{ salon?: string }> };
export default async function StaffPage({ searchParams }: Props) { await requireUser("/salon/staff"); const memberships = await getMySalons() ?? []; const { salon: requested } = await searchParams; const membership = memberships.find((item) => item.salon.id === requested) ?? memberships[0]; if (!membership) return <main className="mx-auto max-w-4xl p-8">Anda belum memiliki keanggotaan salon.</main>; return <main><div className="border-b border-zinc-200 px-4 py-3 text-sm">{membership.salon.name} · Peran: {membership.role}</div><StaffProfiles salonId={membership.salon.id} membershipId={membership.id} role={membership.role} /></main>; }
