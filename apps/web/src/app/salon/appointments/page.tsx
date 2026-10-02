import type { Metadata } from "next";
import { getMySalons, requireUser } from "@/lib/auth/server-session";
import AppointmentCalendar from "@/components/salon/AppointmentCalendar";
export const metadata: Metadata = { title: "Janji Temu — Salon SaaS" };
export const dynamic = "force-dynamic";
type Props = { searchParams: Promise<{ salon?: string }> };
export default async function AppointmentsPage({ searchParams }: Props) {
  await requireUser("/salon/appointments"); const memberships = (await getMySalons()) ?? []; const { salon: requested } = await searchParams;
  const membership = memberships.find((item) => item.salon.id === requested) ?? memberships[0];
  if (!membership) return <main className="mx-auto max-w-3xl px-6 py-12"><h1 className="text-2xl font-semibold">Janji Temu</h1><p className="mt-3 text-sm text-zinc-600">Anda belum memiliki keanggotaan salon.</p></main>;
  return <main><div className="border-b border-zinc-200 px-4 py-3 text-sm">{membership.salon.name} · Peran: {membership.role}</div><AppointmentCalendar salonId={membership.salon.id} /></main>;
}
