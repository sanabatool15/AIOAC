"use client";
import { useState } from "react";
import Link from "next/link";
import { Receipt } from "lucide-react";
import { buttonVariants, Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/state";
import { useToast } from "@/components/ui/toast";
import { loadFlow } from "@/lib/billing-flow";
import { cn } from "@/lib/utils";
import { BillingFrame, Money, SummaryRow } from "./billing-frame";

// Screen 25: billing step 4, done. The receipt comes from the payment response, not from the page URL.
export function DoneStep() {
  const toast = useToast();
  const [receipt] = useState(() => loadFlow().receipt);
  const planName = receipt?.planLabel.split(",")[0];

  return (
    <BillingFrame step={4}>
      {!receipt ? (
        <div className="w-[620px] max-w-full self-start pt-5">
          <EmptyState
            icon={<Receipt />}
            title="No receipt to show"
            body="Start from Usage and plan to choose a plan."
          />
          <Link
            href="/account/usage"
            className={cn(buttonVariants({ size: "action" }), "mt-4")}
          >
            Go to Usage and plan
          </Link>
        </div>
      ) : (
        <div className="flex w-[620px] max-w-full flex-col items-center gap-[18px] pt-5">
          <div
            aria-hidden
            className="flex size-[72px] items-center justify-center rounded-full border-2 border-brand-light text-[28px] font-semibold leading-[normal] text-success"
          >
            ✓
          </div>
          <h1 className="text-[28px] font-semibold leading-[normal] text-ink">
            You are on {planName}
          </h1>
          <p className="text-sm leading-[normal] text-muted">
            Payment received. Your new limits are active now.
          </p>
          <Card
            variant="green"
            className="gap-1.5 overflow-clip p-[22px]"
            aria-label="Receipt"
            data-testid="receipt"
          >
            <h2 className="text-xs font-semibold leading-[normal] text-muted">
              RECEIPT
            </h2>
            <dl className="flex flex-col">
              <SummaryRow label="Invoice" value={receipt.invoice} />
              <SummaryRow label="Date" value={receipt.date} />
              <SummaryRow
                label="Plan"
                value={receipt.planLabel.replace(", ", ", ")}
              />
              <SummaryRow label="Paid with" value={receipt.paidWith} />
              <hr className="my-1 h-px border-0 bg-border" />
              <SummaryRow
                label="Total paid"
                value={Money(receipt.totalUsd)}
                strong
              />
            </dl>
          </Card>
          <div className="flex items-start gap-2.5">
            <Button
              variant="outline"
              size="action"
              onClick={() => toast("Invoice download is mocked in this build.")}
            >
              Download invoice
            </Button>
            <Link
              href="/"
              className={cn(
                buttonVariants({ size: "action" }),
                "rounded-[9px]",
              )}
            >
              Back to chat
            </Link>
          </div>
          <p className="text-sm leading-[normal] text-muted">
            A copy was sent to {receipt.email}
          </p>
        </div>
      )}
    </BillingFrame>
  );
}
