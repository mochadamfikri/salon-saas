import { describe, expect, it } from "vitest";
import { customerPayload, validateCustomerInput } from "./customer-records";

describe("customer record input", () => {
  it("requires a trimmed, nonblank name for create and rejects null name on patch", () => {
    expect(validateCustomerInput({ full_name: "  " }, true)).toHaveProperty("full_name");
    expect(validateCustomerInput({ full_name: null }, false)).toHaveProperty("full_name");
    expect(validateCustomerInput({ full_name: "Walk-in" }, true)).toEqual({});
  });
  it("normalizes email and nullable fields while preserving omitted PATCH values", () => {
    expect(customerPayload({ full_name: " Jane ", email: " JANE@EXAMPLE.COM ", phone: null }, true)).toEqual({ full_name: "Jane", email: "jane@example.com", phone: null });
    expect(customerPayload({ notes: null }, false)).toEqual({ notes: null });
    expect(customerPayload({}, false)).toEqual({});
  });
  it("allows duplicate contact values without special validation", () => {
    expect(validateCustomerInput({ full_name: "One", email: "same@example.com", phone: "same" }, true)).toEqual({});
  });
});
