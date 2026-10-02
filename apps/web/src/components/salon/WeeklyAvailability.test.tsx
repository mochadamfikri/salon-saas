// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WeeklyAvailability from "./WeeklyAvailability";

const profile = { id: "profile-1", membership_id: "member-1", display_name: "Ayu", phone: null, bio: null, photo_url: null, is_bookable: true, created_at: "", updated_at: "" };
const slot = { id: "slot-1", staff_profile_id: "profile-1", day_of_week: 0, start_time: "09:00:00", end_time: "12:00:00", is_available: true, created_at: "", updated_at: "" };
function mockFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("staff-profiles")) return Response.json({ profiles: [profile] });
    if (init?.method === "POST") return Response.json({ slot }, { status: 201 });
    if (init?.method === "PATCH") return Response.json({ slot });
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return Response.json({ slots: [slot] });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("WeeklyAvailability", () => {
  beforeEach(() => vi.restoreAllMocks());
  it("shows weekly slots and allows own staff profile to add a slot", async () => {
    const fetchMock = mockFetch();
    render(<WeeklyAvailability salonId="salon-1" membershipId="member-1" role="staff" />);
    await waitFor(() => expect(screen.getAllByLabelText("Mulai")[0]).toHaveValue("09:00"));
    fireEvent.change(screen.getByLabelText("Hari"), { target: { value: "1" } });
    fireEvent.change(screen.getAllByLabelText("Mulai").at(-1)!, { target: { value: "12:00" } });
    fireEvent.change(screen.getAllByLabelText("Selesai").at(-1)!, { target: { value: "14:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Tambah jadwal" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/availability"), expect.objectContaining({ method: "POST" })));
  });
  it("keeps staff read-only for another profile and surfaces overlap conflicts", async () => {
    mockFetch();
    const otherProfile = { ...profile, membership_id: "other-member" };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input).endsWith("staff-profiles") ? Response.json({ profiles: [otherProfile] }) : Response.json({ slots: [slot] })));
    render(<WeeklyAvailability salonId="salon-1" membershipId="member-1" role="staff" />);
    await waitFor(() => expect(screen.getAllByLabelText("Mulai")[0]).toHaveValue("09:00"));
    expect(screen.queryByRole("button", { name: "Tambah jadwal" })).not.toBeInTheDocument();
  });
});
