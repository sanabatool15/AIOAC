"use client";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { TopBar } from "./top-bar";

const STEPS = [
  {
    title: "Describe what you want to predict",
    body: "Say it in your own words, for example: which customers may stop buying. No technical terms needed.",
  },
  {
    title: "Approve a dataset",
    body: "I find a free open dataset, or you upload your own CSV. You look at it and approve it before I use it. A free test shows a first honest result.",
  },
  {
    title: "Pay a small sandbox hold only if you like the price",
    body: "You get a price estimate first. If you agree, PayPal (sandbox, test money only) holds up to a maximum. You pay for the compute used, and the success fee only if the result is verified. The rest is released.",
  },
] as const;

// First-run page: three short steps and a Start button. Static, no backend.
export function WelcomeScreen() {
  return (
    <section aria-label="Welcome" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={<h2 className="text-sm font-normal leading-[normal] text-muted">Welcome</h2>} />
      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto p-8">
        <div className="flex h-fit w-[640px] max-w-full flex-col gap-5">
          <div className="flex flex-col gap-1 leading-[normal]">
            <h1 className="text-[28px] font-semibold text-ink">Welcome to AIOAC</h1>
            <p className="text-sm text-muted">Three steps from an idea to a working prediction model.</p>
          </div>
          <ol className="flex flex-col gap-3">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <Card variant={i === 2 ? "peach" : "plain"} className="flex-row items-start gap-4 p-5">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-sm font-semibold text-white">
                    {i + 1}
                  </span>
                  <div className="flex min-w-px flex-1 flex-col gap-1">
                    <h2 className="text-base font-semibold text-ink">{s.title}</h2>
                    <p className="text-sm leading-5 text-ink-2">{s.body}</p>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
          <p className="text-xs text-muted">Everything here is an estimate until it has been checked. Nothing is promised, and only test money is used.</p>
          <div>
            <Link href="/" className={cn(buttonVariants({ size: "action" }))}>
              Start
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
