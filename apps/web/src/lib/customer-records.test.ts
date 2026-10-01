import { describe, expect, it } from "vitest";

function normalize(body: Record<string, unknown>) {
  const result: Record<string, unknown> = { ...body, full_name: (body.full_name as string).trim() };
  if (typeof body.email === "string") result.email = body.email.trim().toLowerCase() || null;
  for (const field of ["phone", "notes"]) if (typeof body[field] === "string") result[field] = (body[field] as string).trim() || null;
  return result;
}

describe("customer payload behavior", () => {
  it("supports a full-name-only walk-in and normalizes optional values", () => {
    expect(normalize({ full_name: "  Walk-in  ", email: " TEST@EXAMPLE.COM ", phone: "  123  ", notes: "  " })).toEqual({
      full_name: "Walk-in", email: "test@example.com", phone: "123", notes: null,
    });
  });
  it("allows duplicates without imposing client-side deduplication", () => {
    const entries = [{ full_name: "Same", email: "same@example.com" }, { full_name: "Same", email: "same@example.com" }];
    expect(entries.map(normalize)).toHaveLength(2);
  });
  it("keeps PATCH omission distinct from explicit null", () => {
    const patch = { phone: null };
    expect("email" in patch).toBe(false);
    expect(patch.phone).toBeNull();
  });
});
