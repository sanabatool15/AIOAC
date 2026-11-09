import { PayCancel } from "@/components/shell/pay-return";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Payment cancelled" };

// PayPal's cancel address (backend setting PAYPAL_CANCEL_URL).
export default function PayCancelPage() {
  return <PayCancel />;
}
