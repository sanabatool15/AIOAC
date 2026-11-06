import { USE_MOCK_API } from "./config";

// Mock session (stands in for the httpOnly cookie the FastAPI backend will set).
const KEY = "aioac.session";
const listeners = new Set<() => void>();

export function subscribeSession(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

// ---- Real mode: the signed-in state comes from GET /auth/me (the httpOnly cookie is the truth). Memory only. ----
export interface SessionUser {
  id: string;
  email: string;
  org_id?: string | null;
}
type RealState = { status: "unknown" | "in" | "out"; user: SessionUser | null };
let real: RealState = { status: "unknown", user: null };
// Browser memory that belongs to one user (see api-real.ts). Wiped whenever the signed-in user changes.
const USER_MEMORY = [
  ["sessionStorage", "aioac.pay"],
  ["localStorage", "aioac.lastProject"],
] as const;

export function clearUserMemory() {
  for (const [store, key] of USER_MEMORY) {
    try {
      (store === "localStorage" ? localStorage : sessionStorage).removeItem(key);
    } catch {
      /* storage blocked or not in a browser */
    }
  }
}
function setReal(next: RealState) {
  real = next;
  listeners.forEach((l) => l());
}
export function setRealUser(user: SessionUser) {
  if (real.user?.id !== user.id) clearUserMemory();
  setReal({ status: "in", user });
}
export function clearRealUser() {
  clearUserMemory();
  setReal({ status: "out", user: null });
}
export function getRealSnapshot(): "unknown" | "in" | "out" {
  return real.status;
}
export function getRealUser(): SessionUser | null {
  return real.user;
}

// Send the browser to the login screen, remembering where it was. Never loops: does nothing on /login or /signup.
export function redirectToLogin(path?: string) {
  if (typeof window === "undefined") return;
  const here = path ?? window.location.pathname + window.location.search;
  if (/^\/(login|signup)(\/|\?|$)/.test(here)) return;
  // A full page load on purpose: it also drops every in-memory screen state of the previous user.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}
// Only same-site paths are allowed as a return target.
export function safeNext(raw: string | null | undefined): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") && !raw.startsWith("/\\") ? raw : "/";
}

export function getSessionSnapshot(): "unknown" | "in" | "out" {
  if (!USE_MOCK_API) return real.status;
  try {
    return localStorage.getItem(KEY) === "1" ? "in" : "out";
  } catch {
    return "out";
  }
}

export function setSession(on: boolean) {
  try {
    if (on) localStorage.setItem(KEY, "1");
    else localStorage.removeItem(KEY);
  } catch {
    /* storage blocked: session lasts only for this page */
  }
  listeners.forEach((l) => l());
}

// Mock "first run" flag: set at sign-up, cleared once the first chat starts (screen 35).
const FIRST_KEY = "aioac.firstrun";

export function getFirstRunSnapshot(): boolean {
  try {
    return localStorage.getItem(FIRST_KEY) === "1";
  } catch {
    return false;
  }
}

export function setFirstRun(on: boolean) {
  try {
    if (on) localStorage.setItem(FIRST_KEY, "1");
    else localStorage.removeItem(FIRST_KEY);
  } catch {
    /* storage blocked */
  }
  listeners.forEach((l) => l());
}
