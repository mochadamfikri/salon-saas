// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ServiceCatalog from "./ServiceCatalog";

const item = { id: "svc1", salon_id: "salon-valid", name: "Cut", description: null, category: null, duration_minutes: 30, price_amount: "9999999999.99", currency: "IDR", is_active: true, created_at: "", updated_at: "" };
const response = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status, headers: { "content-type": "application/json" } });

describe("ServiceCatalog role-aware interface", () => {
  beforeEach(() => vi.unstubAllGlobals());
  it("renders state, decimal string and mutation controls for owner", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ services: [item] })));
    render(<ServiceCatalog salonId="salon-valid" role="owner" />);
    expect(await screen.findByText("Aktif")).toBeInTheDocument();
    expect(screen.getByText(/IDR 9999999999\.99/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });
  it("renders services read-only for staff", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ services: [item] })));
    render(<ServiceCatalog salonId="salon-valid" role="staff" />);
    await screen.findByText("Cut");
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nonaktifkan" })).not.toBeInTheDocument();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });
  it("validates create form locally and retains exact price text", async () => {
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => { void url; void options; return response({ services: [] }); });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<ServiceCatalog salonId="salon-valid" role="manager" />);
    await user.type(screen.getByLabelText("Nama layanan"), "Cut");
    await user.type(screen.getByLabelText("Durasi (menit)"), "45");
    await user.type(screen.getByLabelText("Harga"), "9999999999.99");
    await user.click(screen.getByRole("button", { name: "Tambah layanan" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([, options]) => options?.method === "POST")).toBe(true));
    const createRequest = fetchMock.mock.calls.find(([, options]) => options?.method === "POST");
    expect(JSON.parse(String(createRequest?.[1]?.body))).toMatchObject({ price_amount: "9999999999.99", currency: "IDR" });
  });
  it("uses explicit null on clearing optional nullable fields", async () => {
    const fetchMock = vi.fn(async (_url: string, options?: RequestInit) => {
      if (options?.method === "PATCH") return response({ service: item });
      return response({ services: [item] });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<ServiceCatalog salonId="salon-valid" role="owner" />);
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    await user.click(screen.getByLabelText("Hapus deskripsi (kirim null)"));
    await user.click(screen.getByLabelText("Hapus kategori (kirim null)"));
    await user.click(screen.getByRole("button", { name: "Simpan perubahan" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/svc1"), expect.objectContaining({ method: "PATCH" })));
    const patch = fetchMock.mock.calls.find(([, options]) => options?.method === "PATCH");
    expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({ description: null, category: null });
  });
});
