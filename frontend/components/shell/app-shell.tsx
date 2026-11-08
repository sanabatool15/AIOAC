"use client";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import { Menu } from "lucide-react";
import { useRealUser, useSession } from "@/lib/hooks";
import { me } from "@/lib/api-real";
import { DESKTOP_QUERY, drawerIsOpen } from "@/lib/nav";
import { redirectToLogin } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { ToastProvider } from "@/components/ui/toast";
import { NavDrawer } from "./nav-drawer";
import { Logo, Sidebar } from "./sidebar";

export const MAIN_ID = "main-content";

// True from the `lg` width up. The server snapshot is true; the shell only renders for a signed-in user, on the client.
function useIsDesktop() {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(DESKTOP_QUERY);
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => window.matchMedia(DESKTOP_QUERY).matches,
    () => true,
  );
}

// Sidebar on the left from `lg` up, a drawer below it; each route renders its own chat + canvas columns inside <main>.
// Signed-out visitors are sent to the login screen (the app always starts there).
export function AppShell({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const user = useRealUser();
  const pathname = usePathname();
  const desktop = useIsDesktop();
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const open = drawerIsOpen(openedAt, pathname);
  const drawerId = useId();
  const main = useRef<HTMLElement>(null);

  // Ask the server who is signed in (the cookie is the truth).
  useEffect(() => {
    if (session !== "unknown") return;
    me().catch(() => {
      /* server unreachable: stay on the blank screen; a reload retries */
    });
  }, [session]);

  useEffect(() => {
    if (session !== "out") return;
    redirectToLogin();
  }, [session]);

  if (session !== "in") return <div className="h-screen w-full bg-bg" aria-busy="true" />;

  return (
    <ToastProvider>
      <div className="flex h-screen w-full flex-col overflow-hidden bg-bg lg:flex-row">
        <a
          href={`#${MAIN_ID}`}
          onClick={(e) => {
            e.preventDefault();
            main.current?.focus();
          }}
          className="sr-only rounded-md bg-card px-3 py-2 text-body font-medium text-ink shadow-popover focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50"
        >
          Skip to main content
        </a>

        {desktop ? (
          <Sidebar key={user?.id ?? "none"} />
        ) : (
          <>
            <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-surface px-3">
              <Button
                variant="ghost"
                size="icon"
                aria-label="Open navigation"
                aria-expanded={open}
                aria-controls={drawerId}
                aria-haspopup="dialog"
                onClick={() => setOpenedAt(pathname)}
              >
                <Menu aria-hidden />
              </Button>
              <Logo />
            </header>
            <NavDrawer id={drawerId} open={open} onClose={() => setOpenedAt(null)}>
              <Sidebar key={user?.id ?? "none"} drawer onNavigate={() => setOpenedAt(null)} />
            </NavDrawer>
          </>
        )}

        <main ref={main} id={MAIN_ID} tabIndex={-1} className="flex min-h-0 min-w-0 flex-1 outline-none">
          {children}
        </main>
      </div>
    </ToastProvider>
  );
}
