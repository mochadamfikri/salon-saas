import type { BackendSalonCustomerCreateRequest, BackendSalonCustomerUpdateRequest } from "@/lib/auth/contracts";

type CustomerFields = { full_name?: unknown; email?: unknown; phone?: unknown; notes?: unknown };
export type CustomerFieldErrors = Record<string, string>;

export function validateCustomerInput(input: CustomerFields, creating: boolean): CustomerFieldErrors {
  const errors: CustomerFieldErrors = {};
  if (creating || Object.hasOwn(input, "full_name")) {
    if (typeof input.full_name !== "string" || !input.full_name.trim() || input.full_name.trim().length > 200) errors.full_name = "Nama wajib diisi (maksimal 200 karakter).";
  }
  for (const field of ["email", "phone", "notes"] as const) {
    if (!Object.hasOwn(input, field) || input[field] === null) continue;
    if (typeof input[field] !== "string") { errors[field] = "Nilai tidak valid."; continue; }
    const value = input[field].trim();
    const max = field === "email" ? 320 : field === "phone" ? 20 : 1000;
    if (value.length > max) errors[field] = `Maksimal ${max} karakter.`;
  }
  return errors;
}

export function customerPayload(input: CustomerFields, creating: true): BackendSalonCustomerCreateRequest;
export function customerPayload(input: CustomerFields, creating: false): BackendSalonCustomerUpdateRequest;
export function customerPayload(input: CustomerFields, creating: boolean): BackendSalonCustomerCreateRequest | BackendSalonCustomerUpdateRequest {
  const payload: BackendSalonCustomerCreateRequest = { full_name: typeof input.full_name === "string" ? input.full_name.trim() : "" };
  for (const field of ["email", "phone", "notes"] as const) {
    if (!Object.hasOwn(input, field)) continue;
    const value = input[field];
    payload[field] = value === null || (field === "email" && typeof value === "string" && !value.trim()) ? null : field === "email" ? (value as string).trim().toLowerCase() : (value as string).trim();
  }
  if (!creating) delete (payload as BackendSalonCustomerUpdateRequest).full_name;
  if (Object.hasOwn(input, "full_name") && typeof input.full_name === "string") payload.full_name = input.full_name.trim();
  return payload;
}
