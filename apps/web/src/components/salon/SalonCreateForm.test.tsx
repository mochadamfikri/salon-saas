// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalonCreateForm from "./SalonCreateForm";

const pushMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
}));

function json(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("SalonCreateForm", () => {
  beforeEach(() => {
    pushMock.mockReset();
    refreshMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("renders name and slug fields", () => {
    render(<SalonCreateForm />);
    expect(screen.getByLabelText(/salon name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/salon url slug/i)).toBeInTheDocument();
  });

  it("suggests a slug from the salon name", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async () => json(201, { ok: true })));
    render(<SalonCreateForm />);
    await user.type(screen.getByLabelText(/salon name/i), "Glow Studio");
    expect((screen.getByTestId("salon-slug-input") as HTMLInputElement).value).toBe("glow-studio");
  });

  it("validates the slug client-side before submitting", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async () => json(201, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    render(<SalonCreateForm />);
    await user.type(screen.getByLabelText(/salon name/i), "Glow");
    await user.clear(screen.getByTestId("salon-slug-input"));
    await user.type(screen.getByTestId("salon-slug-input"), "BAD SLUG");
    await user.click(screen.getByTestId("salon-create-submit"));
    expect(await screen.findByText(/lowercase/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits with only the name after the suggested slug is cleared", async () => {
    const user = userEvent.setup();
    let sentBody: unknown;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        sentBody = JSON.parse(init.body as string);
        return json(201, {
          ok: true,
          salon: { id: "s1", name: "Glow", slug: "glow-auto", status: "onboarding" },
        });
      }),
    );
    render(<SalonCreateForm />);
    await user.type(screen.getByLabelText(/salon name/i), "Glow");
    // Slug is pre-filled from the name suggestion; clearing it must still submit.
    expect((screen.getByTestId("salon-slug-input") as HTMLInputElement).value).toBe("glow");
    await user.clear(screen.getByTestId("salon-slug-input"));
    await user.click(screen.getByTestId("salon-create-submit"));
    expect(pushMock).toHaveBeenCalledWith("/salon/dashboard");
    expect(sentBody).toEqual({ name: "Glow" });
    expect(sentBody).not.toHaveProperty("slug");
  });

  it("submits an explicit valid slug", async () => {
    const user = userEvent.setup();
    let sentBody: unknown;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        sentBody = JSON.parse(init.body as string);
        return json(201, {
          ok: true,
          salon: { id: "s1", name: "Glow", slug: "glow-custom", status: "onboarding" },
        });
      }),
    );
    render(<SalonCreateForm />);
    await user.type(screen.getByLabelText(/salon name/i), "Glow");
    await user.clear(screen.getByTestId("salon-slug-input"));
    await user.type(screen.getByTestId("salon-slug-input"), "glow-custom");
    await user.click(screen.getByTestId("salon-create-submit"));
    expect(pushMock).toHaveBeenCalledWith("/salon/dashboard");
    expect(sentBody).toEqual({ name: "Glow", slug: "glow-custom" });
  });

  it("creates the salon and navigates to the salon dashboard", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json(201, {
          ok: true,
          salon: { id: "s1", name: "Glow", slug: "glow", status: "onboarding" },
        }),
      ),
    );
    render(<SalonCreateForm />);
    await user.type(screen.getByLabelText(/salon name/i), "Glow");
    await user.click(screen.getByTestId("salon-create-submit"));
    expect(pushMock).toHaveBeenCalledWith("/salon/dashboard");
  });

  it("surfaces a taken slug as a field error", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json(400, {
          ok: false,
          field: "slug",
          message: "This salon URL is already taken. Try another one.",
        }),
      ),
    );
    render(<SalonCreateForm />);
    await user.type(screen.getByLabelText(/salon name/i), "Glow");
    await user.click(screen.getByTestId("salon-create-submit"));
    expect(await screen.findByText(/already taken/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
