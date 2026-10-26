"use client";
import { useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { useAsync } from "@/lib/hooks";
import { getBudget } from "@/lib/mock-api";
import { BudgetPanel } from "./budget-panel";

// Sidebar budget. Remount with key={chatId} to refetch when the active chat changes.
export function BudgetCard({ chatId }: { chatId: string | null }) {
  const { data, error, loading, retry } = useAsync(() => getBudget(chatId));
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);

  if (loading && !data) return <Skeleton className="h-[112px]" />;
  if (error || !data)
    return (
      <ErrorState
        message="Budget unavailable."
        onRetry={retry}
        className="px-2 py-4"
      />
    );

  const holding = data.heldUsd > 0;
  return (
    <Card variant="violet" className="gap-2.5 p-3.5">
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center justify-between text-left"
        aria-label="Open budget details"
      >
        <span className="text-xs font-medium leading-[17px] tracking-[0.2px] text-muted">
          BUDGET
        </span>
        <ChevronDown aria-hidden size={14} className="text-ink-2" />
      </button>
      {holding ? (
        <>
          <div className="flex items-end gap-1.5">
            <span className="text-xl font-semibold leading-[26px] text-ink">
              ${data.heldUsd.toFixed(2)}
            </span>
            <span className="text-[13px] leading-[19px] text-muted">held</span>
          </div>
          <ProgressBar
            label="Budget used"
            value={(data.usedUsd / data.heldUsd) * 100}
          />
          <p className="text-xs leading-[17px] text-muted">
            ${data.usedUsd.toFixed(2)} used · {data.label}
          </p>
        </>
      ) : (
        <>
          <p className="text-base font-semibold leading-[26px] text-ink">
            {data.headline ?? "No funds held"}
          </p>
          {data.progress !== undefined && (
            <ProgressBar label="Budget used" value={data.progress} />
          )}
          <p className="text-xs leading-[17px] text-muted">{data.label}</p>
        </>
      )}
      {open && (
        <BudgetPanel
          chatId={chatId}
          anchor={trigger}
          onClose={() => setOpen(false)}
        />
      )}
    </Card>
  );
}
