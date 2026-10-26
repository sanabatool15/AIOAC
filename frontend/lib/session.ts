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

export function getSessionSnapshot(): "in" | "out" {
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
