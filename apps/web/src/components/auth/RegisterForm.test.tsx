// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RegisterForm from "./RegisterForm";

const pushMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
  useSearchParams: () => ({ get: () => null }),
}));

function okResponse(): Response {
  return new Response(
    JSON.stringify({ ok: true, user: { id: "u1", email: "new@example.com" } }),
    { status: 201, headers: { "content-type": "application/json" } },
  );
}

describe("RegisterForm", () => {
  beforeEach(() => {
    pushMock.mockReset();
    refreshMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("renders the registration fields", () => {
    render(<RegisterForm />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it("enforces the 12-character password minimum", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async () => okResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisterForm />);
    await user.type(screen.getByLabelText(/email/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password/i), "short");
    await user.type(screen.getByLabelText(/confirm password/i), "short");
    await user.click(screen.getByTestId("register-submit"));
    expect(await screen.findByText(/at least 12 characters/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("requires password confirmation to match", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async () => okResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<RegisterForm />);
    await user.type(screen.getByLabelText(/email/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password/i), "a-very-long-password");
    await user.type(screen.getByLabelText(/confirm password/i), "a-different-password");
    await user.click(screen.getByTestId("register-submit"));
    expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("registers and navigates to the dashboard", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async () => okResponse()));
    render(<RegisterForm />);
    await user.type(screen.getByLabelText(/email/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password/i), "a-very-long-password");
    await user.type(screen.getByLabelText(/confirm password/i), "a-very-long-password");
    await user.click(screen.getByTestId("register-submit"));
    expect(pushMock).toHaveBeenCalledWith("/customer/dashboard");
  });

  it("surfaces duplicate-email feedback without leaking tokens", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            ok: false,
            field: "email",
            message: "An account with this email already exists.",
          }),
          { status: 400, headers: { "content-type": "application/json" } },
        ),
      ),
    );
    render(<RegisterForm />);
    await user.type(screen.getByLabelText(/email/i), "taken@example.com");
    await user.type(screen.getByLabelText(/^password/i), "a-very-long-password");
    await user.type(screen.getByLabelText(/confirm password/i), "a-very-long-password");
    await user.click(screen.getByTestId("register-submit"));
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
