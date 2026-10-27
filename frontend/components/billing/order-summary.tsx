import { Card } from "@/components/ui/card";
import { planPrice, planOffers } from "@/lib/mock-api";
import type { BillingCycle, PlanId } from "@/lib/types";
import { Money, SummaryRow } from "./billing-frame";

// Right-hand summary on steps 2 and 3. The backend computes the real total; this mirrors it.
export function OrderSummary({
  plan,
  cycle,
  note,
}: {
  plan: PlanId;
  cycle: BillingCycle;
  note: string;
}) {
  const name = planOffers.find((p) => p.id === plan)!.name;
  const due = planPrice(plan, cycle).due;
  return (
    <Card
      variant="violet"
      className="w-[360px] shrink-0 gap-1.5 self-start overflow-clip p-[22px]"
      data-testid="order-summary"
    >
      <h2 className="text-xs font-semibold leading-[normal] text-muted">
        ORDER SUMMARY
      </h2>
      <dl className="flex flex-col">
        <SummaryRow label={`${name} plan (${cycle})`} value={Money(due)} />
        <SummaryRow label="Tax" value="$0.00" />
        <hr className="my-1 h-px border-0 bg-border" />
        <SummaryRow label="Due today" value={Money(due)} strong />
      </dl>
      <p className="text-sm leading-[18px] text-muted">{note}</p>
    </Card>
  );
}
