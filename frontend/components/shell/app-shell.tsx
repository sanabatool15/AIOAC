"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { USE_MOCK_API } from "@/lib/config";
import { useRealUser, useSession } from "@/lib/hooks";
import { me } from "@/lib/api-real";
import { redirectToLogin } from "@/lib/session";
import { ToastProvider } from "@/components/ui/toast";
import { AddDataProvider } from "./add-data-provider";
import { RealSidebar } from "@/components/real/real-sidebar";
import { Sidebar } from "./sidebar";

// Sidebar on the left; each route renders its own chat + canvas columns.
// Signed-out visitors are sent to the login screen (the app always starts there).
export function AppShell({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const user = useRealUser();
  const router = useRouter();

  // Real mode: ask the server who is signed in (the cookie is the truth). Mock mode: the fake flag.
  useEffect(() => {
    if (USE_MOCK_API || session !== "unknown") return;
    me().catch(() => {
      /* server unreachable: stay on the blank screen; a reload retries */
    });
  }, [session]);

  useEffect(() => {
    if (session !== "out") return;
    if (USE_MOCK_API) router.replace("/login");
    else redirectToLogin();
  }, [session, router]);

  if (session !== "in")
    return <div className="h-screen w-full bg-bg" aria-busy="true" />;

  return (
    <ToastProvider>
      <AddDataProvider>
        <div className="flex h-screen w-full overflow-hidden bg-bg">
          {USE_MOCK_API ? <Sidebar /> : <RealSidebar key={user?.id ?? "none"} />}
          {children}
        </div>
      </AddDataProvider>
    </ToastProvider>
  );
}
