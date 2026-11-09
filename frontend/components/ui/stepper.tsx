import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { stepStates, stepSummary } from "./stepper-logic";

export interface StepperStep {
  id: string;
  label: string;
}

/**
 * Numbered steps: a check on done steps, the current one highlighted. Under
 * the `sm` breakpoint it collapses to "Step 3 of 7" plus the current label.
 */
export function Stepper({
  steps,
  current,
  label = "Progress",
  className,
}: {
  steps: StepperStep[];
  /** 0-based index of the current step. */
  current: number;
  label?: string;
  className?: string;
}) {
  const states = stepStates(steps.length, current);
  const now = steps[Math.min(Math.max(current, 0), steps.length - 1)];
  return (
    <nav aria-label={label} className={className}>
      <p className="text-small text-ink-2 sm:hidden">
        <span className="font-semibold text-ink">{stepSummary(steps.length, current)}</span>
        {now && <span>: {now.label}</span>}
      </p>
      <ol className="hidden items-center gap-2 sm:flex">
        {steps.map((s, i) => {
          const state = states[i];
          return (
            <li key={s.id} aria-current={state === "current" ? "step" : undefined} data-state={state} className="flex min-w-0 items-center gap-2">
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-micro font-semibold",
                  state === "done" && "border-success bg-success text-on-brand",
                  state === "current" && "border-brand bg-brand text-on-brand",
                  state === "upcoming" && "border-border bg-card text-muted",
                )}
              >
                {state === "done" ? <Check aria-hidden className="size-3.5" strokeWidth={3} /> : i + 1}
                {state === "done" && <span className="sr-only">Done: </span>}
              </span>
              <span className={cn("truncate text-small", state === "current" ? "font-semibold text-ink" : state === "done" ? "text-ink-2" : "text-muted")}>{s.label}</span>
              {i < steps.length - 1 && <span aria-hidden className={cn("h-px w-4 shrink-0", state === "done" ? "bg-success" : "bg-border")} />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
