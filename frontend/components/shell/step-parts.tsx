"use client";
import { useCallback, useState } from "react";
import { Card } from "@/components/ui/card";
import { stepStates, stepSummary } from "@/components/ui/stepper-logic";
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
    <p role="alert" className="text-body text-danger">
      {message}
    </p>
  );
}

// The seven project steps (lib/status.ts) on the shared Stepper. `index` is 0-based. Short labels so all seven fit in
// the chat column without being cut off; STEP_LABELS keeps the full names for other screens.
export const SHORT_STEP_LABELS = ["Data", "Check", "Free test", "Target", "Pay", "Train", "Result"] as const;
export const PROJECT_STEPS = STEP_LABELS.map((id, i) => ({ id, label: SHORT_STEP_LABELS[i] ?? id }));

export function ProjectStepper({ index }: { index: number }) {
  const total = PROJECT_STEPS.length;
  const now = Math.min(Math.max(index, 0), total - 1);
  const states = stepStates(total, now);
  return (
    <nav aria-label="Steps" className="flex flex-col gap-2">
      <p className="text-body text-ink">
        <span className="font-semibold">{PROJECT_STEPS[now]?.label}</span>
        <span className="text-muted"> · {stepSummary(total, now)}</span>
      </p>
      <ol className="flex gap-1">
        {PROJECT_STEPS.map((s, i) => (
          <li
            key={s.id}
            data-state={states[i]}
            aria-current={states[i] === "current" ? "step" : undefined}
            className={cn("h-1.5 flex-1 rounded-full", states[i] === "done" && "bg-success", states[i] === "current" && "bg-brand", states[i] === "upcoming" && "bg-border")}
          >
            <span className="sr-only">
              {s.label}: {states[i] === "done" ? "done" : states[i] === "current" ? "current step" : "not yet"}
            </span>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function Row({ label, value, strong }: { label: string; value: React.ReactNode; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 text-body">
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
