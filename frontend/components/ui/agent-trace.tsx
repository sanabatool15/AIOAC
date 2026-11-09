"use client";

import { useEffect, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { Orb, type OrbLook } from "@/components/ui/thinking-orbs";
import { cn } from "@/lib/utils";

// A rail tree of what the agent did, ported from the ThinkingState pattern: a header that folds the list, a trunk with an
// elbow into each row, shimmer on the title while work is live. Colours are tokens only (see globals.css).
// Each kind of work gets its own orb, so the shape of the motion says what is happening.
export function orbFor(text: string): OrbLook {
  if (/search|look|find|download|dataset/i.test(text)) return { state: "searching", variant: "lighthouse" };
  if (/price|quote|estimate|prepar/i.test(text)) return { state: "compacting", variant: "squeeze" };
  if (/test|check|run|train|forecast|pilot|ready|fit/i.test(text)) return { state: "working", variant: "gyro" };
  if (/wait|approv|your ok/i.test(text)) return { state: "waiting" };
  return { state: "reasoning", variant: "twins" };
}

const ROW_H = 32;
const TRUNK_X = 12.5;
const BEND = 6;
const BRANCH_END = 28;

function Rail({ first, last }: { first: boolean; last: boolean }) {
  const branchY = ROW_H / 2;
  const bendY = branchY - BEND;
  return (
    <svg aria-hidden width={BRANCH_END} height={ROW_H} className="pointer-events-none absolute inset-y-0 left-0 h-full overflow-visible stroke-border">
      <line x1={TRUNK_X} y1={first ? -10 : 0} x2={TRUNK_X} y2={bendY} strokeWidth={1} />
      <path d={`M${TRUNK_X} ${bendY} Q${TRUNK_X} ${branchY} ${TRUNK_X + BEND} ${branchY} H${BRANCH_END}`} fill="none" strokeWidth={1} />
      {!last && <line x1={TRUNK_X} y1={bendY} x2={TRUNK_X} y2="100%" strokeWidth={1} />}
    </svg>
  );
}

// The newest line types itself out, so a change in what the assistant is doing is seen, not just swapped.
function Typed({ text, on }: { text: string; on: boolean }) {
  const [n, setN] = useState(on ? 0 : text.length);
  useEffect(() => {
    if (!on || n >= text.length) return;
    const id = setInterval(() => setN((v) => Math.min(text.length, v + 2)), 22);
    return () => clearInterval(id);
  }, [on, n, text.length]);
  return <>{on ? text.slice(0, n) : text}</>;
}

export function AgentTrace({
  steps,
  working,
  title,
  seconds,
  className,
}: {
  steps: string[];
  working: boolean;
  title: string;
  seconds?: number; // how long it has been working, shown at the right of the title
  className?: string;
}) {
  const [manual, setManual] = useState<boolean | null>(null);
  const open = manual ?? working;
  return (
    <div className={cn("flex w-full flex-col text-small", className)}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setManual(!open)}
        className="group flex h-7 w-full items-center gap-2 rounded-sm text-left text-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        {working ? <Orb {...orbFor(steps[steps.length - 1] ?? title)} size={28} className="shrink-0 text-brand" /> : <Check aria-hidden className="size-4 shrink-0 text-success" />}
        <span className={cn("min-w-0 truncate", working && "font-medium text-ink-2")}>{title}</span>
        <ChevronDown aria-hidden className={cn("size-3.5 shrink-0 transition-transform duration-150", open ? "" : "-rotate-90")} />
        {working && seconds !== undefined && <span className="ml-auto shrink-0 text-micro tabular-nums text-muted">{seconds}s</span>}
      </button>
      <div className={cn("grid transition-[grid-template-rows,opacity] duration-150 ease-out", open ? "grid-rows-[1fr] opacity-100" : "pointer-events-none grid-rows-[0fr] opacity-0")}>
        <div className="min-h-0 overflow-hidden">
          <ol className="flex flex-col pl-1 pt-0.5" role="status" aria-live="polite">
            {steps.map((t, i) => {
              const isNow = working && i === steps.length - 1;
              return (
                <li key={`${i}-${t}`} data-live-step className="relative flex items-center motion-safe:animate-row-in" style={{ minHeight: ROW_H, paddingLeft: 56 }}>
                  <Rail first={i === 0} last={i === steps.length - 1} />
                  <span aria-hidden className="absolute flex size-4 items-center justify-center" style={{ left: 32, top: ROW_H / 2 - 8 }}>
                    {isNow ? <Orb {...orbFor(t)} size={20} className="text-brand" /> : <Check className="size-3.5 text-success" strokeWidth={3} />}
                  </span>
                  <span className={cn("min-w-0", isNow ? "text-ink" : "text-muted")}>
                    <Typed text={t} on={isNow} />
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </div>
  );
}
