"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { choiceQuery, loadFlow, saveFlow } from "@/lib/billing-flow";
import { payPlan, planOffers, planPrice } from "@/lib/mock-api";
import type { BillingCycle, PlanId } from "@/lib/types";
import { BillingFrame, Money, SummaryRow } from "./billing-frame";
import { OrderSummary } from "./order-summary";

const changeLink =
  "rounded text-sm font-semibold leading-[normal] text-ink outline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-brand";

// Screen 24: billing step 3, review and confirm. Paying is the only action that charges; it needs the terms ticked.
export function ReviewStep({
  choice,
}: {
  choice: { plan: PlanId; cycle: BillingCycle };
}) {
  const router = useRouter();
  const [flow] = useState(loadFlow);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const q = choiceQuery(choice);
  const name = planOffers.find((p) => p.id === choice.plan)!.name;
  const price = planPrice(choice.plan, choice.cycle);
  // Direct visits fall back to the saved default card, as in the design.
  const paidWith =
    flow.method === "paypal"
      ? "PayPal account"
      : `${flow.cardBrand ?? "Visa"} ending ${flow.cardLast4 ?? "4242"}`;

  async function pay() {
    setBusy(true);
    setFailure(null);
    try {
      const receipt = await payPlan({
        plan: choice.plan,
        cycle: choice.cycle,
        method: flow.method ?? "card",
        cardLast4: flow.cardLast4 ?? "4242",
        cardBrand: flow.cardBrand ?? "Visa",
      });
      saveFlow({ receipt });
      router.push("/billing/done");
    } catch (e) {
      setFailure(
        e instanceof Error
          ? `${e.message} You were not charged.`
          : "Payment did not go through. You were not charged.",
      );
      setBusy(false);
    }
  }

  return (
    <BillingFrame step={3}>
      <div className="flex w-[620px] max-w-full flex-col gap-4">
        <h1 className="text-[28px] font-semibold leading-[normal] text-ink">
          Review and confirm
        </h1>
        <p className="text-sm leading-[normal] text-muted">
          Check everything before you pay.
        </p>
        <Card className="gap-2 overflow-clip" aria-label="Plan">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold leading-[normal] text-muted">
              PLAN
            </h2>
            <Link href="/billing/plan" className={changeLink}>
              Change<span className="sr-only"> plan</span>
            </Link>
          </div>
          <dl>
            <SummaryRow
              label={`${name}, billed ${choice.cycle}`}
              value={`${Money(price.due)} / ${choice.cycle === "yearly" ? "year" : "month"}`}
            />
            <SummaryRow
              label="Next renewal"
              value={
                choice.cycle === "yearly" ? "Oct 24, 2027" : "Nov 24, 2026"
              }
            />
          </dl>
        </Card>
        <Card className="gap-2 overflow-clip" aria-label="Payment method">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold leading-[normal] text-muted">
              PAYMENT METHOD
            </h2>
            <Link href={`/billing/payment?${q}`} className={changeLink}>
              Change<span className="sr-only"> payment method</span>
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <span
              aria-hidden
              className="h-[30px] w-11 shrink-0 rounded-md border border-border bg-surface"
            />
            <p className="min-w-px flex-1 text-sm font-semibold leading-[normal] text-ink">
              {paidWith}
            </p>
          </div>
        </Card>
        <div className="rounded-[14px] border border-border bg-surface p-4">
          <Checkbox id="terms" checked={agreed} onCheckedChange={setAgreed}>
            <span className="leading-[19px]">
              I agree to the Terms and the Billing policy. Job charges only
              happen when a target is verified.
            </span>
          </Checkbox>
        </div>
        {failure && (
          <p
            role="alert"
            className="rounded-lg border border-danger bg-white px-3.5 py-2.5 text-sm leading-[normal] text-ink"
          >
            {failure}
          </p>
        )}
        <div className="flex items-start justify-between">
          <Button
            variant="outline"
            size="action"
            onClick={() => router.push(`/billing/payment?${q}`)}
          >
            Back
          </Button>
          <Button
            size="action"
            className="rounded-[9px]"
            disabled={!agreed || busy}
            onClick={pay}
          >
            {busy
              ? "Paying…"
              : failure
                ? `Try again · Pay ${Money(price.due)}`
                : `Pay ${Money(price.due)}`}
          </Button>
        </div>
      </div>
      <OrderSummary
        plan={choice.plan}
        cycle={choice.cycle}
        note="You will get an invoice by email right away."
      />
    </BillingFrame>
  );
}
