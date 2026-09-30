import type { Metadata } from "next";

import SalonCreateForm from "@/components/salon/SalonCreateForm";
import { requireUser } from "@/lib/auth/server-session";

export const metadata: Metadata = {
  title: "Create salon — Salon SaaS",
  description: "Create a new salon and become its owner.",
};

export const dynamic = "force-dynamic";

export default async function SalonCreatePage() {
  await requireUser("/salon/create");
  return <SalonCreateForm />;
}
