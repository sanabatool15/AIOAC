import Link from "next/link";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const STEPS = ["Plan", "Payment", "Review", "Done"];

// Header shared by the four billing steps (screens 22-25): logo, 4-step tracker, close.
export function BillingFrame({
  step,
  children,
}: {
  step: 1 | 2 | 3 | 4;
  children: React.ReactNode;
}) {
  return (
    <>
      <header className="flex h-[68px] shrink-0 items-center justify-between border-b border-border bg-surface px-8">
        <div className="flex w-[200px] items-center gap-2.5">
          <span
            aria-hidden
            className="size-[26px] rounded-[7px] bg-brand-gradient shadow-btn-primary"
          />
          <span className="text-base font-semibold leading-[normal] text-ink">
            AIOAC
          </span>
        </div>
        <ol aria-label="Steps" className="flex items-center gap-2.5">
          {STEPS.map((label, i) => {
            const n = i + 1;
            const state = n < step ? "done" : n === step ? "current" : "next";
            return (
              <li
                key={label}
                aria-current={state === "current" ? "step" : undefined}
                data-state={state}
                className="flex items-center gap-2.5"
              >
                {i > 0 && (
                  <span
                    aria-hidden
                    className={cn(
                      "h-0.5 w-9",
                      n <= step ? "bg-brand-gradient" : "bg-border",
                    )}
                  />
                )}
                <span
                  className={cn(
                    "flex size-6 items-center justify-center rounded-xl border text-xs font-semibold leading-[normal]",
                    state === "done" &&
                      "border-brand-light bg-white text-success shadow-glow",
                    state === "current" &&
                      "border-brand-light bg-brand-gradient text-white shadow-glow",
                    state === "next" &&
                      (n === 4
                        ? "border-border bg-white text-muted"
                        : "border-white bg-border text-muted"),
                  )}
                >
                  {state === "done" ? (
                    <>
                      <span aria-hidden>✓</span>
                      <span className="sr-only">Completed</span>
                    </>
                  ) : (
                    n
                  )}
                </span>
                <span
                  className={cn(
                    "text-sm leading-[normal] whitespace-nowrap",
                    state === "current"
                      ? "font-semibold text-ink"
                      : state === "done"
                        ? "text-ink"
                        : "text-muted",
                  )}
                >
                  {label}
                </span>
              </li>
            );
          })}
        </ol>
        <div className="flex w-[200px] justify-end">
          <Link
            href="/account/usage"
            className="inline-flex items-center gap-1.5 rounded text-sm leading-[normal] text-muted outline-offset-2 hover:text-ink focus-visible:outline-2 focus-visible:outline-brand"
          >
            Close <X aria-hidden className="size-3.5" />
          </Link>
        </div>
      </header>
      <main className="flex min-h-0 flex-1 justify-center gap-8 overflow-y-auto py-9">
        {children}
      </main>
    </>
  );
}

export const Money = (n: number) => `$${n.toFixed(2)}`;

export function SummaryRow({
  label,
  value,
  strong,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-start justify-between py-[5px] text-sm leading-[normal] whitespace-nowrap",
        strong ? "font-semibold text-ink" : "",
      )}
    >
      <dt className={strong ? "" : "text-muted"}>{label}</dt>
      <dd className={strong ? "" : "font-medium text-ink"}>{value}</dd>
    </div>
  );
}
