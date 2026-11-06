"use client";
import { useCallback, useState } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { STEP_LABELS } from "@/lib/status";

// Run an async click action with busy + plain error text.
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, run, setError };
}

export function ErrorLine({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-sm leading-5 text-danger">
      {message}
    </p>
  );
}

export function Stepper({ index }: { index: number }) {
  return (
    <ol aria-label="Steps" className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {STEP_LABELS.map((label, i) => (
        <li
          key={label}
          aria-current={i === index ? "step" : undefined}
          className={cn(
            "font-medium",
            i < index && "text-success",
            i === index && "font-semibold text-brand-ink",
            i > index && "text-pending",
          )}
        >
          {i + 1}. {label}
        </li>
      ))}
    </ol>
  );
}

export function Row({ label, value, strong }: { label: string; value: React.ReactNode; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className={cn("text-right text-ink", strong && "font-semibold")}>{value}</dd>
    </div>
  );
}

export function Panel({
  title,
  children,
  variant,
  label,
}: {
  title: string;
  children: React.ReactNode;
  variant?: "plain" | "violet" | "peach" | "mint" | "green" | "red" | "amber" | "blue";
  label?: string;
}) {
  return (
    <Card variant={variant} aria-label={label ?? title}>
      <h2 className="text-base font-semibold leading-[normal] text-ink">{title}</h2>
      {children}
    </Card>
  );
}
