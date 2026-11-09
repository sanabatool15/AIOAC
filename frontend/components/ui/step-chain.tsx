"use client";
import { useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tag } from "./tag";
import type { StepState } from "./stepper-logic";

export interface ChainStep {
  id: string;
  label: string;
  state: StepState;
  /** Plain facts under the step. A step with none is not expandable. */
  items: string[];
}

// The journey as a vertical chain: a check on finished steps, a ring on the current one, an empty circle on what is
// still to come. Each step opens to the facts behind it. Only the current step starts open. Nothing here moves on its
// own: a step is "current" because the server says so, never because a timer ran.
export function StepChain({ steps, label }: { steps: ChainStep[]; label: string }) {
  return (
    <ol aria-label={label} className="flex flex-col">
      {steps.map((s, i) => (
        <ChainRow key={`${s.id}-${s.state}`} step={s} last={i === steps.length - 1} />
      ))}
    </ol>
  );
}

function ChainRow({ step, last }: { step: ChainStep; last: boolean }) {
  const [open, setOpen] = useState(step.state === "current");
  const expandable = step.items.length > 0;
  const name = cn("text-body", step.state === "current" ? "font-semibold text-ink" : step.state === "done" ? "font-medium text-ink-2" : "text-muted");
  return (
    <li data-state={step.state} aria-current={step.state === "current" ? "step" : undefined} className="flex gap-3">
      <div className="flex flex-col items-center">
        <span
          className={cn(
            "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
            step.state === "done" && "border-success bg-success text-on-brand",
            step.state === "current" && "border-brand bg-card",
            step.state === "upcoming" && "border-border bg-card",
          )}
        >
          {step.state === "done" && <Check aria-hidden className="size-3" strokeWidth={3} />}
          {step.state === "current" && <span aria-hidden className="size-2 rounded-full bg-brand" />}
          <span className="sr-only">{step.state === "done" ? "Done" : step.state === "current" ? "Current step" : "Not yet"}</span>
        </span>
        {!last && <span aria-hidden className={cn("mt-1 w-px flex-1", step.state === "done" ? "bg-success" : "bg-border")} />}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 pb-3">
        <div className="flex min-h-6 items-center gap-2">
          {expandable ? (
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
              className={cn(name, "flex items-center gap-1 rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand")}
            >
              {step.label}
              <ChevronDown aria-hidden className={cn("size-3.5 text-muted transition-transform", open && "rotate-180")} />
            </button>
          ) : (
            <span className={name}>{step.label}</span>
          )}
          {step.state === "current" && <Tag variant="brand">Now</Tag>}
        </div>
        {expandable && open && (
          <ul className="flex flex-col gap-1">
            {step.items.map((t) => (
              <li key={t} className="flex items-start gap-2 text-small text-ink-2">
                <span aria-hidden className="mt-1.5 size-1 shrink-0 rounded-full bg-muted" />
                <span className="min-w-0 flex-1">{t}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}
