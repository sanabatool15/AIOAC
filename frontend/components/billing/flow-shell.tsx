"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ToastProvider } from "@/components/ui/toast";
import { useSession } from "@/lib/hooks";

export function FlowShell({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const router = useRouter();
  useEffect(() => {
    if (session === "out") router.replace("/login");
  }, [session, router]);
  if (session !== "in")
    return <div className="h-screen w-full bg-bg" aria-busy="true" />;
  return (
    <ToastProvider>
      <div className="flex h-screen w-full flex-col overflow-hidden bg-bg">
        {children}
      </div>
    </ToastProvider>
  );
}
