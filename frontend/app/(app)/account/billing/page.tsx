import { BillingScreen } from "@/components/shell/billing-screen";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Billing history" };

export default function BillingPage() {
  return <BillingScreen />;
}
