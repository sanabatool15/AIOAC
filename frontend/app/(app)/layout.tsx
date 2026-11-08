import type { Metadata } from "next";
import { AppShell } from "@/components/shell/app-shell";

// Pages set a short title; the template adds the product name ("Projects | AIOAC").
export const metadata: Metadata = {
  title: { template: "%s | AIOAC", default: "AIOAC" },
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
