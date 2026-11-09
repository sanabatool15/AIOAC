import { UsageScreen } from "@/components/shell/usage-screen";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Usage" };

export default function UsagePage() {
  return <UsageScreen />;
}
