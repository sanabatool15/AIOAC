// The welcome page is shown once, right after the first sign-up in this browser. The flag lives in localStorage and
// is never the truth about anything important: if storage is blocked the page is simply skipped.
export const WELCOME_KEY = "aioac.welcomeSeen";

type Store = Pick<Storage, "getItem" | "setItem">;
function defaultStore(): Store | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

export function welcomeSeen(store: Store | null = defaultStore()): boolean {
  try {
    return store ? store.getItem(WELCOME_KEY) === "1" : true; // no storage: do not nag
  } catch {
    return true;
  }
}
export function markWelcomeSeen(store: Store | null = defaultStore()): void {
  try {
    store?.setItem(WELCOME_KEY, "1");
  } catch {
    /* storage blocked: skip */
  }
}

// Where to go after a successful sign-in. Only a first SIGN-UP sees the welcome page; a login never does.
export function pathAfterAuth(mode: "login" | "signup", next: string, store: Store | null = defaultStore()): string {
  if (mode === "signup" && !welcomeSeen(store)) {
    markWelcomeSeen(store);
    return "/welcome";
  }
  return next;
}
