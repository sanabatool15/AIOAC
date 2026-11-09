"use client";
import { ShieldCheck } from "lucide-react";
import { LinkButton } from "@/components/ui/button";
import type { BProject } from "@/lib/api";
import { projectMoney } from "@/lib/money-summary";

// In the chat, where the reader is looking: the price is ready, here is how paying works, one button to go and do it.
export function PayPrompt({ project }: { project: BProject }) {
  const m = projectMoney(project);
  return (
    <section aria-label="Ready to pay" className="flex flex-col gap-3 rounded-lg border border-card-line bg-grad-card p-4 shadow-card sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <ShieldCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-brand" />
        <div className="flex flex-col gap-0.5">
          <p className="text-body font-semibold text-ink">Your price is ready</p>
          <p className="text-body text-ink-2">
            PayPal holds up to {m.cap}. You are only charged if your target is verified. If it is missed, the hold is released.
          </p>
        </div>
      </div>
      <LinkButton href={`/c/${project.id}/pay`} className="shrink-0">
        Review and pay
      </LinkButton>
    </section>
  );
}
