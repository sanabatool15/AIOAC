"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { USE_MOCK_API } from "@/lib/config";
import { useSession } from "@/lib/hooks";
import { setSession } from "@/lib/session";
import { ToastProvider } from "@/components/ui/toast";
import { AddDataProvider } from "./add-data-provider";
import { RealSidebar } from "@/components/real/real-sidebar";
import { Sidebar } from "./sidebar";

// Sidebar on the left; each route renders its own chat + canvas columns.
// Signed-out visitors are sent to the login screen (the app always starts there).
export function AppShell({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session !== "out") return;
    // Real mode has no login yet (the backend has none): open a demo session instead of the login screen.
    if (!USE_MOCK_API) setSession(true);
    else router.replace("/login");
  }, [session, router]);

  if (session !== "in")
    return <div className="h-screen w-full bg-bg" aria-busy="true" />;

  return (
    <ToastProvider>
      <AddDataProvider>
        <div className="flex h-screen w-full overflow-hidden bg-bg">
          {USE_MOCK_API ? <Sidebar /> : <RealSidebar />}
          {children}
        </div>
      </AddDataProvider>
    </ToastProvider>
  );
}
