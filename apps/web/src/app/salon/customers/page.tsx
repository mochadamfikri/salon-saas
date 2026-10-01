import type { Metadata } from "next";
import CustomerRecords from "@/components/salon/CustomerRecords";
import { getMySalons, requireUser } from "@/lib/auth/server-session";

export const metadata: Metadata = { title: "Pelanggan — Salon SaaS" };
export const dynamic = "force-dynamic";
type Props = { searchParams: Promise<{ salon?: string }> };
export default async function SalonCustomersPage({ searchParams }: Props) {
  await requireUser("/salon/customers");
  const memberships = (await getMySalons()) ?? [];
  const { salon: requestedSalonId } = await searchParams;
  const membership = memberships.find((item) => item.salon.id === requestedSalonId) ?? memberships[0];
  if (!membership) return <main className="mx-auto max-w-3xl px-6 py-12"><h1 className="text-2xl font-semibold">Pelanggan</h1><p className="mt-3 text-sm text-zinc-600">Anda belum memiliki keanggotaan salon.</p></main>;
  return <main><div className="border-b border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">{membership.salon.name} · Peran: {membership.role}</div><CustomerRecords salonId={membership.salon.id} /></main>;
}
