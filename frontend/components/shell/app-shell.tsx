"use client";
import { useEffect } from "react";
import { useRealUser, useSession } from "@/lib/hooks";
import { me } from "@/lib/api-real";
import { redirectToLogin } from "@/lib/session";
import { ToastProvider } from "@/components/ui/toast";
import { AddDataProvider } from "./add-data-provider";
import { Sidebar } from "./sidebar";

// Sidebar on the left; each route renders its own chat + canvas columns.
// Signed-out visitors are sent to the login screen (the app always starts there).
export function AppShell({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const user = useRealUser();

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

  if (session !== "in")
    return <div className="h-screen w-full bg-bg" aria-busy="true" />;

  return (
    <ToastProvider>
      <AddDataProvider>
        <div className="flex h-screen w-full overflow-hidden bg-bg">
          <Sidebar key={user?.id ?? "none"} />
          {children}
        </div>
      </AddDataProvider>
    </ToastProvider>
  );
}
