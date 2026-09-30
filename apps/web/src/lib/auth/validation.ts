/**
 * Shared input validation for auth + tenant forms.
 *
 * These run on BOTH client (UX) and server/BFF (defense in depth).
 * The backend remains the authority — these never replace backend checks.
 */

export const PASSWORD_MIN_LENGTH = 12;
export const PASSWORD_MAX_LENGTH = 128;

export const SALON_NAME_MIN_LENGTH = 1;
export const SALON_NAME_MAX_LENGTH = 120;

export const SLUG_MIN_LENGTH = 3;
export const SLUG_MAX_LENGTH = 80;

/** Mirrors the backend slug pattern: ^[a-z0-9]+(?:-[a-z0-9]+)*$ */
export const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Unicode-safe length: counts code points, not UTF-16 code units. */
export function unicodeLength(value: string): number {
  return Array.from(value).length;
}

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email: string): ValidationResult {
  const trimmed = email.trim();
  if (!trimmed) return { valid: false, error: "Email is required." };
  if (trimmed.length > 320) return { valid: false, error: "Email is too long." };
  if (!EMAIL_PATTERN.test(trimmed)) return { valid: false, error: "Enter a valid email address." };
  return { valid: true };
}

/**
 * Password policy (matches backend contract):
 * - 12..128 characters (unicode-safe counting)
 * - NO mandatory uppercase / symbol / digit rules (per spec: arbitrary
 *   complexity rules degrade entropy and are forbidden)
 */
export function validatePassword(password: string): ValidationResult {
  const len = unicodeLength(password);
  if (len === 0) return { valid: false, error: "Password is required." };
  if (len < PASSWORD_MIN_LENGTH) {
    return { valid: false, error: `Password must be at least ${PASSWORD_MIN_LENGTH} characters.` };
  }
  if (len > PASSWORD_MAX_LENGTH) {
    return { valid: false, error: `Password must be at most ${PASSWORD_MAX_LENGTH} characters.` };
  }
  return { valid: true };
}

export function validateSalonName(name: string): ValidationResult {
  const trimmed = name.trim();
  if (trimmed.length < SALON_NAME_MIN_LENGTH) return { valid: false, error: "Salon name is required." };
  if (trimmed.length > SALON_NAME_MAX_LENGTH) {
    return { valid: false, error: `Salon name must be at most ${SALON_NAME_MAX_LENGTH} characters.` };
  }
  return { valid: true };
}

export function validateSlug(slug: string): ValidationResult {
  const normalized = slug.trim().toLowerCase();
  if (normalized.length < SLUG_MIN_LENGTH) {
    return { valid: false, error: `Slug must be at least ${SLUG_MIN_LENGTH} characters.` };
  }
  if (normalized.length > SLUG_MAX_LENGTH) {
    return { valid: false, error: `Slug must be at most ${SLUG_MAX_LENGTH} characters.` };
  }
  if (!SLUG_PATTERN.test(normalized)) {
    return {
      valid: false,
      error: "Slug may only contain lowercase letters, numbers, and single hyphens.",
    };
  }
  return { valid: true };
}

/** Suggest a backend-compatible slug from a salon name (UX helper only). */
export function suggestSlug(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-")
    .slice(0, SLUG_MAX_LENGTH);
}

/**
 * Open-redirect guard for `?next=` continuation paths.
 * Only same-origin absolute paths are allowed.
 */
export function isSafeRedirectPath(path: string | null | undefined): path is string {
  if (!path) return false;
  return path.startsWith("/") && !path.startsWith("//") && !path.includes("\\");
}

export function safeRedirectPath(path: string | null | undefined, fallback: string): string {
  return isSafeRedirectPath(path) ? path : fallback;
}
