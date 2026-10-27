"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import { getPlans, planPrice } from "@/lib/mock-api";
import type { BillingCycle, PlanOffer } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BillingFrame } from "./billing-frame";

// Screen 22: billing step 1, choose a plan.
export function PlanStep() {
  const router = useRouter();
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(() => getPlans());
  const [cycle, setCycle] = useState<BillingCycle>("monthly");

  return (
    <BillingFrame step={1}>
      <div className="flex w-[960px] max-w-full flex-col gap-5 px-4">
        <div className="flex flex-col items-center gap-1.5 text-center leading-[normal]">
          <h1 className="text-[28px] font-semibold text-ink">Choose a plan</h1>
          <p className="text-sm text-muted">
            Every plan includes the free baseline and the pay-only-if-verified
            a capped price on eligible jobs.
          </p>
        </div>
        <div className="flex justify-center">
          <div
            role="group"
            aria-label="Billing period"
            className="flex gap-0.5 rounded-[20px] bg-surface p-[3px]"
          >
            {(["monthly", "yearly"] as const).map((c) => (
              <Chip
                key={c}
                variant={cycle === c ? "primary" : "outline"}
                aria-pressed={cycle === c}
                onClick={() => setCycle(c)}
                className={cycle === c ? "rounded-[20px]" : undefined}
              >
                {c === "monthly" ? "Monthly" : "Yearly  -20%"}
              </Chip>
            ))}
          </div>
        </div>
        {loading && !data ? (
          <div
            aria-busy="true"
            aria-label="Loading plans"
            className="flex gap-4"
          >
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[380px] flex-1" />
            ))}
          </div>
        ) : error || !data ? (
          <ErrorState
            message={error?.message ?? "Plans unavailable."}
            onRetry={retry}
          />
        ) : (
          <div className="flex items-start gap-4">
            {data.plans.map((p) => (
              <PlanCard
                key={p.id}
                plan={p}
                cycle={cycle}
                current={data.current === p.id}
                onChoose={() =>
                  p.monthlyUsd === 0
                    ? toast("Downgrades are handled by support (demo).")
                    : router.push(
                        `/billing/payment?plan=${p.id}&cycle=${cycle}`,
                      )
                }
              />
            ))}
          </div>
        )}
        <p className="text-center text-sm leading-[normal] text-muted">
          The plan fee covers limits and features. Training is still
          pay-per-result: you are charged for a job only if its target is
          verified.
        </p>
      </div>
    </BillingFrame>
  );
}

function PlanCard({
  plan,
  cycle,
  current,
  onChoose,
}: {
  plan: PlanOffer;
  cycle: BillingCycle;
  current: boolean;
  onChoose: () => void;
}) {
  const featured = !!plan.badge;
  const price = planPrice(plan.id, cycle).perMonth;
  return (
    <article
      aria-label={`${plan.name} plan`}
      className={cn(
        "flex min-w-px flex-1 flex-col gap-3 overflow-clip rounded-xl p-6 shadow-card",
        featured ? "surface-violet border-2" : "border border-border bg-card",
      )}
    >
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold leading-[normal] text-ink">
          {plan.name}
        </h2>
        {current ? (
          <Tag>CURRENT</Tag>
        ) : (
          plan.badge && <Tag variant="brand">{plan.badge}</Tag>
        )}
      </div>
      <p className="flex items-end gap-1.5 leading-[normal] whitespace-nowrap">
        <span className="text-[28px] font-semibold text-ink">
          ${Number.isInteger(price) ? price : price.toFixed(2)}
        </span>
        <span className="text-sm text-muted">/month</span>
      </p>
      <p className="text-sm leading-5 text-muted">{plan.blurb}</p>
      <hr className="h-px border-0 bg-border" />
      <ul className="flex flex-col gap-3">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <span
              aria-hidden
              className="font-semibold leading-[normal] text-success"
            >
              ✓
            </span>
            <span className="min-w-px flex-1 leading-[19px] text-ink">{f}</span>
          </li>
        ))}
      </ul>
      <Button
        size="action"
        variant={featured && !current ? "primary" : "outline"}
        className={cn(
          "w-full disabled:opacity-100",
          featured && !current && "rounded-[9px]",
        )}
        disabled={current}
        onClick={onChoose}
      >
        {current
          ? "Current plan"
          : plan.monthlyUsd === 0
            ? "Downgrade"
            : `Choose ${plan.name}`}
      </Button>
    </article>
  );
}
