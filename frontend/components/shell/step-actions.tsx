"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { targetFromOutOf100, toBaseline } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import * as real from "@/lib/api-real";
import { ErrorLine, useAction } from "./step-parts";

interface Props {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

// The one thing to do next on each free step. A click calls the real route; the page then re-reads the project.

export function ReadinessAction({ project, onChanged }: Props) {
  const { busy, error, run } = useAction();
  return (
    <Card aria-label="Check your data" className="gap-3 p-4">
      <h2 className="text-section text-ink">Check your data</h2>
      <p className="text-body text-ink-2">
        I will look for missing values, copies and other problems, and give your data a grade. This is free.
      </p>
      <div>
        <Button
         
          disabled={busy}
          onClick={() =>
            run(async () => {
              await real.runReadiness(project.id);
              await onChanged();
            })
          }
        >
          {busy ? "Checking…" : "Check my data"}
        </Button>
      </div>
      <ErrorLine message={error} />
    </Card>
  );
}

export function FreeTestAction({ project, onChanged }: Props) {
  const { busy, error, run } = useAction();
  return (
    <Card aria-label="Run the free test" className="gap-3 p-4">
      <h2 className="text-section text-ink">Run the free test</h2>
      <p className="text-body text-ink-2">
        I will train a small first model here, at no cost, and test it on rows it has not seen. It is a first signal, not the final result.
      </p>
      <div>
        <Button
         
          disabled={busy}
          onClick={() =>
            run(async () => {
              await real.runBaseline(project.id);
              await onChanged();
            })
          }
        >
          {busy ? "Testing… this can take a little while" : "Run the free test"}
        </Button>
      </div>
      <ErrorLine message={error} />
    </Card>
  );
}

// "Right out of 100" goes to the backend as 0 to 1 (adapters.targetFromOutOf100). No price cap field, no precision or recall.
export function TargetAction({
  project,
  onChanged,
  initial,
  intro,
  title,
  buttonLabel,
  mustBeAbove,
}: Props & { initial?: number | null; intro?: string; title?: string; buttonLabel?: string; mustBeAbove?: number | null }) {
  const { busy, error, run } = useAction();
  const base = toBaseline(project);
  const [value, setValue] = useState(String(initial ?? Math.min(95, (base?.right ?? 70) + 5)));
  const target = targetFromOutOf100(Number(value));
  const tooLow = mustBeAbove != null && !(Number(value) > mustBeAbove);
  return (
    <Card variant="highlight" aria-label={title ?? "Pick your target"} className="gap-3 p-4">
      <h2 className="text-section text-ink">{title ?? "Pick your target"}</h2>
      <p className="text-body text-ink-2">
        {intro ??
          "How many predictions out of 100 do you want to be right? A small free pilot estimates the chance a full run gets there."}
      </p>
      <div className="max-w-40">
        <Field label="Right out of 100" htmlFor="target-n">
          <Input
            id="target-n"
            type="number"
            min={1}
            max={99}
            inputMode="numeric"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-invalid={target === null}
          />
        </Field>
      </div>
      {tooLow && (
        <p className="text-micro text-muted" role="status">
          The new target must be higher than the {mustBeAbove} out of 100 already reached.
        </p>
      )}
      <div>
        <Button
         
          disabled={busy || target === null || tooLow}
          onClick={() =>
            run(async () => {
              await real.runPilot(project.id, target as number);
              await onChanged();
            })
          }
        >
          {busy ? "Running the free pilot (about half a minute)…" : (buttonLabel ?? "Run the free pilot")}
        </Button>
      </div>
      <ErrorLine message={error} />
    </Card>
  );
}
