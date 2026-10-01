// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StaffProfiles from "./StaffProfiles";

const profile = { id: "profile-1", membership_id: "member-1", display_name: "Ayu", phone: null, bio: null, photo_url: null, is_bookable: true, created_at: "", updated_at: "" };
const response = (payload: unknown) => new Response(JSON.stringify(payload), { status: 200, headers: { "content-type": "application/json" } });

describe("StaffProfiles role-aware interface", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("shows profile mutation and assignment controls to managers", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/services") && url.includes("profile-1") ? response({ assignments: [] }) : url.endsWith("/staff-profiles") ? response({ profiles: [profile] }) : url.endsWith("/services") ? response({ services: [] }) : response({ members: [] })));
    render(<StaffProfiles salonId="salon-1" membershipId="member-2" role="manager" />);
    expect(await screen.findByRole("button", { name: "Nonaktifkan untuk booking" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Simpan profil" })).toBeInTheDocument();
  });

  it("allows staff to edit only their own personal profile fields", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/services") && url.includes("profile-1") ? response({ assignments: [] }) : url.endsWith("/staff-profiles") ? response({ profiles: [profile] }) : response({ services: [] })));
    render(<StaffProfiles salonId="salon-1" membershipId="member-1" role="staff" />);
    expect(await screen.findByRole("button", { name: "Simpan profil" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /booking/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("does not expose another staff member's edit controls", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/services") && url.includes("profile-1") ? response({ assignments: [] }) : url.endsWith("/staff-profiles") ? response({ profiles: [profile] }) : response({ services: [] })));
    render(<StaffProfiles salonId="salon-1" membershipId="member-other" role="staff" />);
    await screen.findByText("Ayu");
    expect(screen.queryByRole("button", { name: "Simpan profil" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
