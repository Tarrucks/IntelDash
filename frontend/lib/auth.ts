/**
 * Token storage.
 *
 * v1 stores the JWT in `localStorage`. Cookies with HttpOnly would be
 * the production move, but they require backend changes to set the
 * cookie, and the brief explicitly says to keep auth boring for v1.
 *
 * Reads are SSR-safe — return `null` during build.
 */

const KEY = "aperture.jwt";
const ROLE_KEY = "aperture.role";

export function readToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY);
}

export function readRole(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ROLE_KEY);
}

export function writeAuth(token: string, role: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, token);
  window.localStorage.setItem(ROLE_KEY, role);
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
  window.localStorage.removeItem(ROLE_KEY);
}

export function isAuthenticated(): boolean {
  return readToken() != null;
}
