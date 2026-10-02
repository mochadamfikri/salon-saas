import { NextRequest } from "next/server";
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { ACCESS_COOKIE } from "@/lib/auth/cookies";
import { POST } from "./route";

const context = {
  params: Promise.resolve({
    salonId: "path-salon",
    profileId: "profile-1",
  }),
};

const req = (body: unknown) =>
  new NextRequest("http://localhost/api", {
    method: "POST",
    headers: {
      cookie: `${ACCESS_COOKIE}=token`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });

describe("toggle bookable BFF", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it.each([null, "true", [], [true]])(
    "rejects non-object JSON payload %# with 422",
    async (body) => {
      const mock = vi.fn();
      vi.stubGlobal("fetch", mock);

      const response = await POST(
        req(body),
        context,
      );

      expect(response.status).toBe(422);
      expect(mock).not.toHaveBeenCalled();
    },
  );

  it("rejects non-boolean is_bookable with 422", async () => {
    const mock = vi.fn();
    vi.stubGlobal("fetch", mock);

    const response = await POST(
      req({ is_bookable: "true" }),
      context,
    );

    expect(response.status).toBe(422);
    expect(mock).not.toHaveBeenCalled();
  });
});
