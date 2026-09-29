import { describe, expect, it, vi } from "vitest";

import { checkApiConnectivity } from "./api";

describe("checkApiConnectivity", () => {
  it("returns connected when the health endpoint returns ok", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );

    await expect(checkApiConnectivity("http://api.test", fetcher)).resolves.toEqual({
      status: "connected",
    });
  });

  it("returns unavailable when the API returns a non-success response", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 503 }));

    await expect(checkApiConnectivity("http://api.test", fetcher)).resolves.toEqual({
      status: "unavailable",
      message: "API returned 503",
    });
  });

  it("returns unavailable when the API returns an unexpected response", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ state: "unknown" }), { status: 200 }),
    );

    await expect(checkApiConnectivity("http://api.test", fetcher)).resolves.toEqual({
      status: "unavailable",
      message: "API returned an unexpected response",
    });
  });

  it("returns unavailable when the API cannot be reached", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("connection refused"));

    await expect(checkApiConnectivity("http://api.test", fetcher)).resolves.toEqual({
      status: "unavailable",
      message: "API is unavailable",
    });
  });
});
