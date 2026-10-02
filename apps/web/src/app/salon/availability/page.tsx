import type { Metadata } from "next";
import { getMySalons, requireUser } from "@/lib/auth/server-session";
import WeeklyAvailability from "@/components/salon/WeeklyAvailability";
export const metadata: Metadata = { title: "Ketersediaan Staf — Salon SaaS" };
export const dynamic = "force-dynamic";
type Props = { searchParams: Promise<{ salon?: string }> };
export default async function AvailabilityPage({ searchParams }: Props) {
  await requireUser("/salon/availability");
  const memberships = (await getMySalons()) ?? [];
  const { salon: requested } = await searchParams;
  const membership = memberships.find((item) => item.salon.id === requested) ?? memberships[0];
  if (!membership) return <main className="mx-auto max-w-4xl p-8">Anda belum memiliki keanggotaan salon.</main>;
  return <main><div className="border-b border-zinc-200 px-4 py-3 text-sm">{membership.salon.name} · Peran: {membership.role}</div><WeeklyAvailability salonId={membership.salon.id} membershipId={membership.id} role={membership.role} /></main>;
}
