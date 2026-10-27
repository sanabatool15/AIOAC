import { PaymentStep } from "@/components/billing/payment-step";
import { parseChoice } from "@/lib/billing-flow";

export default async function BillingPaymentPage({
  searchParams,
}: {
  searchParams: Promise<{ plan?: string; cycle?: string }>;
}) {
  return <PaymentStep choice={parseChoice(await searchParams)} />;
}
