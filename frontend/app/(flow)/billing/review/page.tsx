import { ReviewStep } from "@/components/billing/review-step";
import { parseChoice } from "@/lib/billing-flow";

export default async function BillingReviewPage({
  searchParams,
}: {
  searchParams: Promise<{ plan?: string; cycle?: string }>;
}) {
  return <ReviewStep choice={parseChoice(await searchParams)} />;
}
