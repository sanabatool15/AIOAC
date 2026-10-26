"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import { getBudgetBreakdown, stopJob } from "@/lib/mock-api";
import type { BudgetBreakdown } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "./confirm-dialog";

const usd = (n: number) => `$${n.toFixed(2)}`;

const stateTag: Record<
  BudgetBreakdown["rows"][number]["state"],
  { label: string; variant: "brand" | "muted" }
> = {
  done: { label: "DONE", variant: "muted" },
  running: { label: "RUNNING", variant: "brand" },
  locked: { label: "LOCKED", variant: "muted" },
  reserved: { label: "RESERVED", variant: "muted" },
};

// Screen 11: popover opened from the sidebar Budget card. Non-modal; Escape or outside click closes.
export function BudgetPanel({
  chatId,
  onClose,
  anchor,
}: {
  chatId: string | null;
  onClose: () => void;
  anchor: React.RefObject<HTMLElement | null>;
}) {
  const { data, error, loading, retry } = useAsync(
    () => getBudgetBreakdown(chatId),
    chatId,
  );
  const ref = useRef<HTMLDivElement>(null);
  const [confirming, setConfirming] = useState(false);
  const toast = useToast();
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (confirming) return;
      if (ref.current?.contains(t) || anchor.current?.contains(t)) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [onClose, anchor, confirming]);

  return (
    <>
      <div
        ref={ref}
        role="dialog"
        aria-label="Budget for this job"
        className="fixed left-[276px] top-[70px] z-40 flex w-[420px] flex-col gap-3.5 rounded-2xl border border-border bg-surface p-5 shadow-popover"
      >
        {loading && !data ? (
          <div
            className="flex flex-col gap-3"
            aria-busy="true"
            aria-label="Loading budget"
          >
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-14" />
            <Skeleton className="h-32" />
          </div>
        ) : error ? (
          <ErrorState message="Budget details unavailable." onRetry={retry} />
        ) : !data ? (
          <EmptyState
            icon={<Wallet />}
            title="No budget yet"
            body="Nothing is held until you approve a performance agreement."
          />
        ) : (
          <Body
            data={data}
            onStop={() => setConfirming(true)}
            onPayments={() => {
              onClose();
              router.push("/account/billing");
            }}
          />
        )}
      </div>
      {confirming && (
        <ConfirmDialog
          title="Stop this job?"
          body="Training stops now and your PayPal hold is voided. You pay $0 for anything not yet verified."
          confirmLabel="Stop job"
          onCancel={() => setConfirming(false)}
          onConfirm={async () => {
            if (chatId) await stopJob(chatId);
            setConfirming(false);
            onClose();
            toast("Job stopped. Your PayPal hold was voided.");
          }}
        />
      )}
    </>
  );
}

function Body({
  data,
  onStop,
  onPayments,
}: {
  data: BudgetBreakdown;
  onStop: () => void;
  onPayments: () => void;
}) {
  const bar = data.rows.filter((r) => r.allocationUsd > 0);
  return (
    <>
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold leading-[normal] text-ink">
          Budget for this job
        </h2>
        <Tag variant="brand">LIVE</Tag>
      </div>
      <dl className="flex gap-6 text-left font-semibold leading-[normal]">
        {[
          ["MAX HELD", data.maxHeldUsd],
          ["USED SO FAR", data.usedUsd],
          ["CHARGED TODAY", data.chargedTodayUsd],
        ].map(([label, value]) => (
          <div key={label} className="flex min-w-px flex-1 flex-col gap-0.5">
            <dt className="text-xs whitespace-nowrap text-muted">{label}</dt>
            <dd className="text-xl whitespace-nowrap text-ink">
              {usd(value as number)}
            </dd>
          </div>
        ))}
      </dl>
      <div
        role="img"
        aria-label="Split of the held amount across experiments and buffer"
        className="flex w-full gap-[3px]"
      >
        {bar.map((r) => (
          <div
            key={r.id}
            style={{ flexGrow: r.allocationUsd, flexBasis: 0 }}
            className={cn(
              "h-3 rounded-[4px]",
              r.state === "running" && "bg-brand-gradient",
              r.state === "locked" && "bg-bar-target",
              r.state === "reserved" && "border border-border bg-surface",
            )}
          />
        ))}
      </div>
      <ul aria-label="Allocations" className="flex flex-col">
        {data.rows.map((r) => (
          <li
            key={r.id}
            data-state={r.state}
            className="flex items-center gap-3 border-b border-border py-2.5"
          >
            <div className="flex min-w-px flex-1 flex-col gap-px leading-[normal]">
              <span className="text-sm font-semibold text-ink">{r.title}</span>
              <span className="text-xs text-muted">{r.detail}</span>
            </div>
            <span className="text-sm font-semibold leading-[normal] whitespace-nowrap text-ink">
              {r.amountLabel}
            </span>
            <Tag variant={stateTag[r.state].variant}>
              {stateTag[r.state].label}
            </Tag>
          </li>
        ))}
      </ul>
      <p className="text-sm leading-[18px] text-muted">{data.rule}</p>
      <p className="rounded-lg bg-surface p-2.5 text-xs font-medium leading-4 text-ink">
        {data.policy}
      </p>
      <div className="flex items-start gap-2">
        <Button variant="outline" size="md" onClick={onStop}>
          Stop job
        </Button>
        <Button variant="outline" size="md" onClick={onPayments}>
          View payments
        </Button>
      </div>
    </>
  );
}
