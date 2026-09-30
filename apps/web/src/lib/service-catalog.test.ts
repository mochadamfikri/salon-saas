import { describe, expect, it } from "vitest";
import { createServicePayload, updateServicePayload, validateServiceInput, validateServicePatch } from "./service-catalog";

const valid = { name: "Potong rambut", duration_minutes: 45, price_amount: "9999999999.99", currency: "IDR" };

describe("service catalog input semantics", () => {
  it("accepts the maximum price as an exact decimal string", () => {
    expect(validateServiceInput(valid)).toEqual({});
    expect(createServicePayload(valid).price_amount).toBe("9999999999.99");
  });
  it("rejects price above the Numeric(12,2) maximum", () => {
    expect(validateServiceInput({ ...valid, price_amount: "10000000000.00" })).toHaveProperty("price_amount");
  });
  it("rejects invalid duration values", () => {
    for (const duration of [0, -1, 1.5, "30"]) {
      expect(validateServiceInput({ ...valid, duration_minutes: duration })).toHaveProperty("duration_minutes");
    }
  });
  it("preserves optional empty strings and omits fields only when omitted", () => {
    expect(createServicePayload({ ...valid, description: "", category: "" })).toMatchObject({ description: "", category: "" });
    expect(updateServicePayload({ name: "  Trim  " })).toEqual({ name: "Trim" });
  });
  it("preserves explicit null clear semantics for nullable PATCH fields", () => {
    expect(updateServicePayload({ description: null, category: null })).toEqual({ description: null, category: null });
  });
  it("does not permit null for required update fields in the client contract helper", () => {
    expect(updateServicePayload({ name: null, duration_minutes: null, price_amount: null, currency: null })).toBeNull();
    expect(validateServicePatch({ name: null, description: null })).toHaveProperty("name");
  });
  it("defaults currency through backend omission, without inventing price arithmetic", () => {
    expect(createServicePayload({ name: "Wash", duration_minutes: 30, price_amount: "12.30" })).not.toHaveProperty("currency");
  });
});
