"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/lib/hooks";
import { ToastProvider } from "@/components/ui/toast";
import { AddDataProvider } from "./add-data-provider";
import { Sidebar } from "./sidebar";

// Sidebar on the left; each route renders its own chat + canvas columns.
// Signed-out visitors are sent to the login screen (the app always starts there).
export function AppShell({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session === "out") router.replace("/login");
  }, [session, router]);

  if (session !== "in")
    return <div className="h-screen w-full bg-bg" aria-busy="true" />;

  return (
    <ToastProvider>
      <AddDataProvider>
        <div className="flex h-screen w-full overflow-hidden bg-bg">
          <Sidebar />
          {children}
        </div>
      </AddDataProvider>
    </ToastProvider>
  );
}
