// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginForm from "./LoginForm";

const pushMock = vi.fn();
const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, refresh: refreshMock }),
  useSearchParams: () => ({ get: () => null }),
}));

function okResponse(): Response {
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function errorResponse(message: string): Response {
  return new Response(JSON.stringify({ ok: false, message }), {
    status: 401,
    headers: { "content-type": "application/json" },
  });
}

describe("LoginForm", () => {
  beforeEach(() => {
    pushMock.mockReset();
    refreshMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("renders accessible email and password fields", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByTestId("login-submit")).toBeInTheDocument();
  });

  it("validates email format client-side before submitting", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async () => okResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginForm />);
    await user.type(screen.getByLabelText(/email/i), "not-an-email");
    await user.type(screen.getByLabelText(/password/i), "a-very-long-password");
    await user.click(screen.getByTestId("login-submit"));
    expect(await screen.findByText(/enter a valid email/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits valid credentials and navigates to the dashboard", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async () => okResponse()));
    render(<LoginForm />);
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "a-very-long-password");
    await user.click(screen.getByTestId("login-submit"));
    expect(pushMock).toHaveBeenCalledWith("/customer/dashboard");
  });

  it("shows a generic error for invalid credentials", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async () => errorResponse("Invalid email or password.")));
    render(<LoginForm />);
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "a-very-long-password");
    await user.click(screen.getByTestId("login-submit"));
    expect(await screen.findByText("Invalid email or password.")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("never stores tokens in browser storage", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async () => okResponse()));
    render(<LoginForm />);
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "a-very-long-password");
    await user.click(screen.getByTestId("login-submit"));
    expect(pushMock).toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
