"use client";
import { useCallback, useState } from "react";
import { Card } from "@/components/ui/card";
import { Stepper } from "@/components/ui/stepper";
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

// The seven project steps (lib/status.ts) on the shared Stepper. `index` is 0-based. Short labels so all seven fit in
// the chat column without being cut off; STEP_LABELS keeps the full names for other screens.
export const SHORT_STEP_LABELS = ["Data", "Check", "Free test", "Target", "Pay", "Train", "Result"] as const;
export const PROJECT_STEPS = STEP_LABELS.map((id, i) => ({ id, label: SHORT_STEP_LABELS[i] ?? id }));

export function ProjectStepper({ index }: { index: number }) {
  return <Stepper label="Steps" steps={PROJECT_STEPS} current={index} />;
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
      <h2 className="text-section text-ink">{title}</h2>
      {children}
    </Card>
  );
}
