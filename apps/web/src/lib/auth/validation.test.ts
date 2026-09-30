import { describe, expect, it } from "vitest";

import {
  isSafeRedirectPath,
  safeRedirectPath,
  suggestSlug,
  unicodeLength,
  validateEmail,
  validatePassword,
  validateSalonName,
  validateSlug,
} from "./validation";

describe("validateEmail", () => {
  it("accepts a normal email", () => {
    expect(validateEmail("user@example.com").valid).toBe(true);
  });

  it("rejects empty and malformed emails", () => {
    expect(validateEmail("").valid).toBe(false);
    expect(validateEmail("not-an-email").valid).toBe(false);
    expect(validateEmail("a@b").valid).toBe(false);
  });

  it("rejects overlong emails", () => {
    expect(validateEmail(`${"a".repeat(320)}@x.com`).valid).toBe(false);
  });
});

describe("validatePassword", () => {
  it("accepts a 12-char password without complexity rules", () => {
    expect(validatePassword("alllowercase1").valid).toBe(true);
  });

  it("rejects passwords shorter than 12 chars", () => {
    const r = validatePassword("short1");
    expect(r.valid).toBe(false);
    expect(r.error).toContain("12");
  });

  it("rejects passwords longer than 128 chars", () => {
    expect(validatePassword("a".repeat(129)).valid).toBe(false);
    expect(validatePassword("a".repeat(128)).valid).toBe(true);
  });

  it("counts unicode code points, not UTF-16 units", () => {
    // 11 latin chars + 1 emoji = 12 code points (13 UTF-16 units)
    expect(validatePassword("abcdefghijk😀").valid).toBe(true);
    expect(unicodeLength("😀")).toBe(1);
  });

  it("does not require uppercase, symbols, or digits", () => {
    expect(validatePassword("nouppercase!!").valid).toBe(true);
    expect(validatePassword("123456789012").valid).toBe(true);
  });
});

describe("validateSalonName", () => {
  it("accepts a normal name", () => {
    expect(validateSalonName("Glow Studio").valid).toBe(true);
  });

  it("rejects blank and overlong names", () => {
    expect(validateSalonName("   ").valid).toBe(false);
    expect(validateSalonName("a".repeat(121)).valid).toBe(false);
  });
});

describe("validateSlug", () => {
  it("accepts backend-compatible slugs", () => {
    expect(validateSlug("glow-studio").valid).toBe(true);
    expect(validateSlug("abc").valid).toBe(true);
  });

  it("normalizes case before validating (the form lowercases input too)", () => {
    expect(validateSlug("UPPER").valid).toBe(true);
  });

  it("rejects invalid slugs", () => {
    expect(validateSlug("ab").valid).toBe(false); // too short
    expect(validateSlug("has space").valid).toBe(false);
    expect(validateSlug("-leading").valid).toBe(false);
    expect(validateSlug("trailing-").valid).toBe(false);
    expect(validateSlug("double--hyphen").valid).toBe(false);
  });
});

describe("suggestSlug", () => {
  it("derives a usable slug from a name", () => {
    expect(suggestSlug("Glow Studio & Spa!")).toBe("glow-studio-spa");
  });

  it("strips diacritics and collapses separators", () => {
    expect(suggestSlug("Café  Beauty")).toBe("cafe-beauty");
  });
});

describe("redirect safety", () => {
  it("allows same-origin absolute paths", () => {
    expect(isSafeRedirectPath("/customer/dashboard")).toBe(true);
    expect(isSafeRedirectPath("/invite/accept?token=abc")).toBe(true);
  });

  it("rejects open redirects and junk", () => {
    expect(isSafeRedirectPath(null)).toBe(false);
    expect(isSafeRedirectPath("")).toBe(false);
    expect(isSafeRedirectPath("https://evil.com")).toBe(false);
    expect(isSafeRedirectPath("//evil.com")).toBe(false);
    expect(isSafeRedirectPath("/\\evil")).toBe(false);
  });

  it("falls back safely", () => {
    expect(safeRedirectPath("https://evil.com", "/customer/dashboard")).toBe("/customer/dashboard");
    expect(safeRedirectPath("/salon/dashboard", "/customer/dashboard")).toBe("/salon/dashboard");
  });
});
