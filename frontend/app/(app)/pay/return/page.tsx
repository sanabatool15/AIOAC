import { PayReturn } from "@/components/shell/pay-return";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Payment status" };

// PayPal's return address (backend setting PAYPAL_RETURN_URL).
export default function PayReturnPage() {
  return <PayReturn />;
}
