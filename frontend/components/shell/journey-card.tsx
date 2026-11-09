"use client";
import { Card } from "@/components/ui/card";
import { StepChain, type ChainStep } from "@/components/ui/step-chain";
import { stepStates, stepSummary } from "@/components/ui/stepper-logic";
import { toBaseline, toFindings, toForecast } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import { projectMoney } from "@/lib/money-summary";
import { PROJECT_STEPS } from "./step-parts";

// The facts behind each step, all from the server project. A fact the server has not given is left out, never guessed.
function itemsFor(i: number, p: BProject): string[] {
  const out: string[] = [];
  switch (i) {
    case 0: {
      const d = p.dataset;
      if (d) out.push(`${d.rows.toLocaleString("en-US")} rows, ${d.columns} columns`, `Predicting "${d.target}"`, `From ${d.source}`);
      break;
    }
    case 1: {
      if (p.readiness_grade) out.push(`Data grade ${p.readiness_grade}`);
      out.push(...toFindings(p).slice(0, 2).map((f) => f.text));
      break;
    }
    case 2: {
      const b = toBaseline(p);
      if (b?.right != null) out.push(`First model: ${b.right} out of 100`);
      if (b?.guess != null) out.push(`Simple guess: ${b.guess} out of 100`);
      break;
    }
    case 3: {
      const f = toForecast(p.forecast);
      if (f?.target != null) out.push(`Your target: ${f.target} out of 100`);
      if (f?.expected != null) out.push(`Expected: about ${f.expected} out of 100 (estimate)`);
      if (f?.confidence != null) out.push(`Chance of reaching it: about ${f.confidence}% (estimate)`);
      break;
    }
    case 4: {
      if (p.quote || p.payment) {
        const m = projectMoney(p);
        out.push(`Cap: ${m.cap}`, `Held on PayPal: ${m.held}`);
        if (m.charged !== "Not yet") out.push(`Charged: ${m.charged}`);
      }
      break;
    }
    case 5: {
      if (p.run) out.push(`Run status: ${p.run.status}`);
      break;
    }
  }
  return out;
}

// One card for the whole journey, in the right pane. `index` is the 0-based current step.
export function JourneyCard({ project, index }: { project: BProject; index: number }) {
  const total = PROJECT_STEPS.length;
  // index below 0 means the process has not started: nothing is highlighted yet.
  const started = index >= 0;
  const now = Math.min(Math.max(index, 0), total - 1);
  const states = started ? stepStates(total, now) : Array.from({ length: total }, () => "upcoming" as const);
  const steps: ChainStep[] = PROJECT_STEPS.map((s, i) => ({
    id: s.id,
    label: s.label,
    state: states[i],
    items: states[i] === "upcoming" ? [] : itemsFor(i, project),
  }));
  return (
    <Card aria-label="Your progress" className="gap-3 p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-section text-ink">Your progress</h2>
        <p className="text-small text-muted">
          {started ? `${stepSummary(total, now)}: ${PROJECT_STEPS[now]?.label}` : "Not started"}
        </p>
      </div>
      <StepChain steps={steps} label="Steps" />
    </Card>
  );
}
