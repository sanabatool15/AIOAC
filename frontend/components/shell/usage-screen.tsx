"use client";
import Link from "next/link";
import { CreditCard, Receipt } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useAsync } from "@/lib/hooks";
import { getUsage } from "@/lib/mock-api";
import type { UsageActivity } from "@/lib/types";
import { cn } from "@/lib/utils";
import { TopBar } from "./top-bar";

const eyebrow = "text-xs font-semibold leading-[normal] text-muted";
const cell = "px-3.5 py-[13px] text-sm leading-[normal]";
const STATUS: Record<
  UsageActivity["status"],
  { label: string; variant: "success" | "muted" | "brand" }
> = {
  captured: { label: "Captured", variant: "success" },
  voided: { label: "Voided", variant: "muted" },
  held: { label: "Held", variant: "brand" },
};

// Screen 21: usage and plan (billing overview). Read-only; money state comes from the backend.
export function UsageScreen() {
  const { data, error, loading, retry } = useAsync(() => getUsage());
  return (
    <section
      aria-label="Usage and plan"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <TopBar
        shareStyle="chip"
        left={
          <h2 className="text-sm font-normal leading-[normal] whitespace-pre text-muted">
            {"Account  /  Usage and plan"}
          </h2>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        <div className="flex items-center gap-4">
          <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
            <h1 className="text-[28px] font-semibold text-ink">
              Usage and plan
            </h1>
            <p className="text-sm text-muted">
              Your plan, what you used this month, and how you pay.
            </p>
          </div>
          <Link
            href="/billing/plan"
            className={cn(
              buttonVariants({ size: "md" }),
              "rounded-[9px] font-semibold shadow-glow",
            )}
          >
            Upgrade plan
          </Link>
        </div>
        {loading && !data ? (
          <div
            aria-busy="true"
            aria-label="Loading usage"
            className="flex flex-col gap-4"
          >
            <div className="flex gap-4">
              <Skeleton className="h-[170px] flex-1" />
              <Skeleton className="h-[170px] flex-1" />
            </div>
            <div className="flex gap-4">
              <Skeleton className="h-[130px] flex-1" />
              <Skeleton className="h-[130px] flex-1" />
            </div>
            <Skeleton className="h-[140px]" />
          </div>
        ) : error || !data ? (
          <ErrorState
            message={error?.message ?? "Usage unavailable."}
            onRetry={retry}
          />
        ) : (
          <>
            <div className="flex items-stretch gap-4">
              <Card
                variant="violet"
                className="min-w-px flex-1 gap-2.5 overflow-clip"
                data-testid="current-plan"
              >
                <div className="flex items-center justify-between">
                  <p className={eyebrow}>CURRENT PLAN</p>
                  <Tag variant="brand">{data.plan.badge}</Tag>
                </div>
                <p className="text-[28px] font-semibold leading-[normal] text-ink">
                  {data.plan.name}
                </p>
                <p className="text-sm leading-5 text-muted">
                  {data.plan.blurb}
                </p>
              </Card>
              <Card
                variant="mint"
                className="min-w-px flex-1 overflow-clip"
                data-testid="usage-meters"
              >
                <p className={eyebrow}>THIS MONTH</p>
                {data.meters.map((m) => (
                  <div key={m.id} className="flex flex-col gap-1.5">
                    <div className="flex items-start justify-between text-sm leading-[normal] whitespace-nowrap">
                      <p className="font-semibold text-ink">{m.label}</p>
                      <p className="text-muted">{m.text}</p>
                    </div>
                    <ProgressBar
                      label={m.label}
                      value={(m.used / m.limit) * 100}
                      track="neutral"
                      size="sm"
                    />
                  </div>
                ))}
              </Card>
            </div>
            <div className="flex items-stretch gap-4">
              <Card
                className="min-w-px flex-1 gap-3 overflow-clip"
                data-testid="payment-method"
              >
                <div className="flex items-center justify-between font-semibold leading-[normal]">
                  <p className="text-xs text-muted">PAYMENT METHOD</p>
                  <Link
                    href="/account/billing"
                    className="rounded text-sm text-ink outline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-brand"
                  >
                    Manage
                  </Link>
                </div>
                {data.card ? (
                  <div className="flex items-center gap-3">
                    <span
                      aria-hidden
                      className="h-[30px] w-11 shrink-0 rounded-md border border-border bg-surface"
                    />
                    <div className="flex min-w-px flex-1 flex-col text-sm leading-[normal]">
                      <p className="font-semibold text-ink">
                        {data.card.label}
                      </p>
                      <p className="text-muted">{data.card.expires}</p>
                    </div>
                    {data.card.isDefault && <Tag variant="brand">DEFAULT</Tag>}
                  </div>
                ) : (
                  <EmptyState
                    icon={<CreditCard />}
                    title="No payment method"
                    body="Add a card before your first agreed job."
                  />
                )}
                <p className="text-sm leading-[18px] text-muted">
                  Your card is only held when you start an agreed job. Nothing
                  is charged unless the target is verified.
                </p>
              </Card>
              <Card
                variant="peach"
                className="min-w-px flex-1 gap-2 overflow-clip"
                data-testid="held-now"
              >
                <p className={eyebrow}>HELD RIGHT NOW</p>
                <p className="text-[28px] font-semibold leading-[normal] text-ink">
                  ${data.heldUsd.toFixed(2)}
                </p>
                <p className="text-sm leading-[18px] text-muted">
                  {data.heldNote}
                </p>
              </Card>
            </div>
            <h2 className={eyebrow}>RECENT ACTIVITY</h2>
            {data.activity.length === 0 ? (
              <EmptyState
                icon={<Receipt />}
                title="No activity yet"
                body="Job receipts appear here after your first agreed job."
              />
            ) : (
              <div className="overflow-clip rounded-xl border border-border bg-card shadow-card">
                <table className="w-full table-fixed border-collapse text-left">
                  <caption className="sr-only">Recent activity</caption>
                  <thead className="bg-surface text-muted">
                    <tr>
                      <th
                        scope="col"
                        className={cn(cell, "w-[130px] font-semibold")}
                      >
                        Date
                      </th>
                      <th
                        scope="col"
                        className={cn(cell, "w-[150px] font-semibold")}
                      >
                        Type
                      </th>
                      <th scope="col" className={cn(cell, "font-semibold")}>
                        Description
                      </th>
                      <th
                        scope="col"
                        className={cn(cell, "w-[110px] font-semibold")}
                      >
                        Amount
                      </th>
                      <th
                        scope="col"
                        className={cn(cell, "w-[110px] font-semibold")}
                      >
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.activity.map((a) => (
                      <tr
                        key={a.id}
                        className="border-b border-border text-ink last:border-b-0"
                      >
                        <td className={cell}>{a.date}</td>
                        <td className={cell}>{a.type}</td>
                        <td className={cell}>{a.description}</td>
                        <td className={cell}>{a.amount}</td>
                        <td className={cell}>
                          <Tag variant={STATUS[a.status].variant}>
                            {STATUS[a.status].label}
                          </Tag>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
