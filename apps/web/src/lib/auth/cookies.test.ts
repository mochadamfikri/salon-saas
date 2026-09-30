import { describe, expect, it } from "vitest";

import {
  ACCESS_COOKIE,
  INVITE_CONTINUATION_COOKIE,
  REFRESH_COOKIE,
  accessCookieAttributes,
  decodeCookieValue,
  expiredCookieAttributes,
  hasAnySessionToken,
  inviteContinuationCookieAttributes,
  parseSessionTokens,
  refreshCookieAttributes,
  withSessionTokens,
} from "./cookies";

describe("cookie attributes", () => {
  it("uses distinct names for access and refresh tokens", () => {
    expect(ACCESS_COOKIE).not.toBe(REFRESH_COOKIE);
  });

  it("is always HttpOnly with SameSite=Lax", () => {
    for (const attrs of [accessCookieAttributes("production"), refreshCookieAttributes("test")]) {
      expect(attrs.httpOnly).toBe(true);
      expect(attrs.sameSite).toBe("lax");
      expect(attrs.path).toBe("/");
    }
  });

  it("sets Secure outside development", () => {
    expect(accessCookieAttributes("production").secure).toBe(true);
    expect(accessCookieAttributes("staging").secure).toBe(true);
    expect(accessCookieAttributes("development").secure).toBe(false);
    expect(refreshCookieAttributes(undefined).secure).toBe(true);
  });

  it("gives the access cookie a short lifetime and refresh a long one", () => {
    const access = accessCookieAttributes("production");
    const refresh = refreshCookieAttributes("production");
    expect(access.maxAge).toBeLessThan(refresh.maxAge);
    expect(access.maxAge).toBe(15 * 60);
    expect(refresh.maxAge).toBe(30 * 24 * 60 * 60);
  });

  it("expires cookies immediately for logout", () => {
    expect(expiredCookieAttributes().maxAge).toBe(0);
  });

  it("mirrors the Secure flag of the environment when expiring", () => {
    expect(expiredCookieAttributes("production").secure).toBe(true);
    // A non-secure development cookie must be cleared without Secure,
    // otherwise the browser keeps the original cookie.
    expect(expiredCookieAttributes("development").secure).toBe(false);
  });

  it("scopes the invitation continuation cookie tightly", () => {
    const attrs = inviteContinuationCookieAttributes("production");
    expect(attrs.httpOnly).toBe(true);
    expect(attrs.secure).toBe(true);
    expect(attrs.sameSite).toBe("lax");
    expect(attrs.path).toBe("/invite");
    expect(attrs.maxAge).toBe(10 * 60);
    expect(INVITE_CONTINUATION_COOKIE).not.toBe(ACCESS_COOKIE);
    expect(INVITE_CONTINUATION_COOKIE).not.toBe(REFRESH_COOKIE);
  });
});

describe("parseSessionTokens", () => {
  it("parses both tokens from a cookie header", () => {
    const tokens = parseSessionTokens(`${ACCESS_COOKIE}=aaa; ${REFRESH_COOKIE}=bbb`);
    expect(tokens).toEqual({ accessToken: "aaa", refreshToken: "bbb" });
  });

  it("handles missing header and partial cookies", () => {
    expect(parseSessionTokens(null)).toEqual({ accessToken: undefined, refreshToken: undefined });
    expect(parseSessionTokens("other=1")).toEqual({
      accessToken: undefined,
      refreshToken: undefined,
    });
    const partial = parseSessionTokens(`${REFRESH_COOKIE}=bbb`);
    expect(partial.accessToken).toBeUndefined();
    expect(partial.refreshToken).toBe("bbb");
  });

  it("ignores empty values", () => {
    const tokens = parseSessionTokens(`${ACCESS_COOKIE}=; ${REFRESH_COOKIE}=bbb`);
    expect(tokens.accessToken).toBeUndefined();
    expect(hasAnySessionToken(tokens)).toBe(true);
    expect(hasAnySessionToken({ accessToken: undefined, refreshToken: undefined })).toBe(false);
  });

  it("decodes values written with encodeURIComponent", () => {
    const tokens = parseSessionTokens(`${ACCESS_COOKIE}=${encodeURIComponent("a/b+c")}`);
    expect(tokens.accessToken).toBe("a/b+c");
  });
});

describe("decodeCookieValue", () => {
  it("decodes encoded values and never throws", () => {
    expect(decodeCookieValue(encodeURIComponent("a/b+c"))).toBe("a/b+c");
    expect(decodeCookieValue("plain")).toBe("plain");
    expect(decodeCookieValue("%")).toBe("%");
    expect(decodeCookieValue(undefined)).toBeUndefined();
    expect(decodeCookieValue("")).toBeUndefined();
  });
});

describe("withSessionTokens", () => {
  it("replaces the session pair while keeping other cookies", () => {
    const header = withSessionTokens(`other=1; ${ACCESS_COOKIE}=old`, {
      accessToken: "new-at",
      refreshToken: "new-rt",
    });
    const tokens = parseSessionTokens(header);
    expect(tokens).toEqual({ accessToken: "new-at", refreshToken: "new-rt" });
    expect(header).toContain("other=1");
    expect(header).not.toContain("old");
  });

  it("encodes values so they round-trip", () => {
    const header = withSessionTokens(null, { accessToken: "a/b", refreshToken: undefined });
    expect(parseSessionTokens(header).accessToken).toBe("a/b");
  });
});
