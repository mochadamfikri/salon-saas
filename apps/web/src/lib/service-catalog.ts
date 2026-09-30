import type { BackendSalonServiceCreateRequest, BackendSalonServiceUpdateRequest } from "@/lib/auth/contracts";

export type ServiceFormErrors = Partial<Record<"name" | "description" | "category" | "duration_minutes" | "price_amount" | "currency", string>>;

export function validateServiceInput(input: Record<string, unknown>): ServiceFormErrors {
  const errors: ServiceFormErrors = {};
  if (typeof input.name !== "string" || input.name.trim().length < 1 || input.name.trim().length > 200) {
    errors.name = "Nama wajib diisi (maksimal 200 karakter).";
  }
  if (!Number.isInteger(input.duration_minutes) || (input.duration_minutes as number) <= 0) {
    errors.duration_minutes = "Durasi harus berupa bilangan bulat lebih dari 0 menit.";
  }
  if (typeof input.price_amount !== "string" || !/^(?:0|[1-9]\d{0,9})(?:\.\d{1,2})?$/.test(input.price_amount)) {
    errors.price_amount = "Harga harus berupa angka desimal maksimal 9999999999.99.";
  }
  if (input.currency !== undefined && (typeof input.currency !== "string" || !/^[A-Za-z]{3}$/.test(input.currency))) {
    errors.currency = "Mata uang harus berupa kode 3 huruf.";
  }
  for (const [key, max] of [["description", 1000], ["category", 100]] as const) {
    const value = input[key];
    if (value !== undefined && value !== null && (typeof value !== "string" || value.length > max)) {
      errors[key] = key === "description" ? "Deskripsi maksimal 1000 karakter." : "Kategori maksimal 100 karakter.";
    }
  }
  return errors;
}

export function validateServicePatch(input: Record<string, unknown>): ServiceFormErrors {
  const errors: ServiceFormErrors = {};
  if (Object.keys(input).length === 0) errors.name = "Tidak ada perubahan layanan.";
  if (Object.prototype.hasOwnProperty.call(input, "name") && (typeof input.name !== "string" || input.name.trim().length < 1 || input.name.trim().length > 200)) {
    errors.name = "Nama wajib diisi (maksimal 200 karakter).";
  }
  if (Object.prototype.hasOwnProperty.call(input, "duration_minutes") && (!Number.isInteger(input.duration_minutes) || (input.duration_minutes as number) <= 0)) {
    errors.duration_minutes = "Durasi harus berupa bilangan bulat lebih dari 0 menit.";
  }
  if (Object.prototype.hasOwnProperty.call(input, "price_amount") && (typeof input.price_amount !== "string" || !/^(?:0|[1-9]\d{0,9})(?:\.\d{1,2})?$/.test(input.price_amount))) {
    errors.price_amount = "Harga harus berupa angka desimal maksimal 9999999999.99.";
  }
  if (Object.prototype.hasOwnProperty.call(input, "currency") && (typeof input.currency !== "string" || !/^[A-Za-z]{3}$/.test(input.currency))) {
    errors.currency = "Mata uang harus berupa kode 3 huruf.";
  }
  for (const [key, max] of [["description", 1000], ["category", 100]] as const) {
    const value = input[key];
    if (Object.prototype.hasOwnProperty.call(input, key) && value !== null && (typeof value !== "string" || value.length > max)) {
      errors[key] = key === "description" ? "Deskripsi maksimal 1000 karakter." : "Kategori maksimal 100 karakter.";
    }
  }
  for (const key of ["name", "duration_minutes", "price_amount", "currency"] as const) {
    if (Object.prototype.hasOwnProperty.call(input, key) && input[key] === null) {
      errors[key] = "Kolom ini tidak boleh null.";
    }
  }
  return errors;
}

export function createServicePayload(input: Record<string, unknown>): BackendSalonServiceCreateRequest {
  return {
    name: (input.name as string).trim(),
    duration_minutes: input.duration_minutes as number,
    price_amount: input.price_amount as string,
    ...(input.description !== undefined ? { description: input.description as string | null } : {}),
    ...(input.category !== undefined ? { category: input.category as string | null } : {}),
    ...(input.currency !== undefined ? { currency: (input.currency as string).toUpperCase() } : {}),
  };
}

export function updateServicePayload(input: Record<string, unknown>): BackendSalonServiceUpdateRequest | null {
  const payload: BackendSalonServiceUpdateRequest = {};
  for (const key of ["name", "duration_minutes", "price_amount", "currency", "description", "category"] as const) {
    if (Object.prototype.hasOwnProperty.call(input, key)) {
      const value = input[key];
      if (key === "name" && typeof value === "string") payload.name = value.trim();
      else if (key === "currency" && typeof value === "string") payload.currency = value.toUpperCase();
      else if (key === "duration_minutes" && typeof value === "number") payload.duration_minutes = value;
      else if (key === "price_amount" && typeof value === "string") payload.price_amount = value;
      else if ((key === "description" || key === "category") && (typeof value === "string" || value === null)) payload[key] = value;
    }
  }
  return Object.keys(payload).length ? payload : null;
}
