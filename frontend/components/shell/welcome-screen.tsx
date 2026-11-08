"use client";
import { Card } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { EstimateNote } from "@/components/ui/estimate-note";
import { PageHeader } from "@/components/ui/page-header";
import { TopBar } from "./top-bar";

const STEPS = [
  {
    title: "Describe what you want to predict",
    body: "Say it in your own words, for example: which customers may stop buying.",
  },
  {
    title: "Approve a dataset",
    body: "We find a free open dataset, or you upload your own CSV. You approve it, then a free test shows a first honest result.",
  },
  {
    title: "Pay only if you like the price",
    body: "You see a price estimate first. If you agree, PayPal (sandbox, test money only) holds up to a maximum. You pay for the compute used, and the success fee only if the result is verified. The rest is released.",
  },
] as const;

// First-run page: three short steps and a Start button. Static, no backend.
export function WelcomeScreen() {
  return (
    <section aria-label="Welcome" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={<p className="text-body text-muted">Welcome</p>} />
      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto p-4 sm:p-8">
        <div className="flex h-fit w-full max-w-chat flex-col gap-5">
          <PageHeader title="Welcome to AIOAC" subtitle="Three steps from an idea to a working prediction model." />
          <ol className="flex flex-col gap-3">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <Card className="flex-row items-start gap-4 p-5">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand text-body font-semibold text-on-brand">
                    {i + 1}
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <h2 className="text-section text-ink">{s.title}</h2>
                    <p className="text-body text-ink-2">{s.body}</p>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
          <EstimateNote>Prices and results are estimates, not promises. Only test money is used.</EstimateNote>
          <div>
            <LinkButton href="/" size="lg">
              Start
            </LinkButton>
          </div>
        </div>
      </div>
    </section>
  );
}
