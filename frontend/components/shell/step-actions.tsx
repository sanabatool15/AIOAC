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
      <h2 className="text-base font-semibold leading-[normal] text-ink">Check your data</h2>
      <p className="text-sm leading-5 text-ink-2">
        I will look for missing values, copies and other problems, and give your data a grade. This is free.
      </p>
      <div>
        <Button
          size="md"
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
      <h2 className="text-base font-semibold leading-[normal] text-ink">Run the free test</h2>
      <p className="text-sm leading-5 text-ink-2">
        I will train a small first model here, at no cost, and test it on rows it has not seen. It gives an honest first
        signal. It is not a promise of the final result.
      </p>
      <div>
        <Button
          size="md"
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
}: Props & { initial?: number | null; intro?: string }) {
  const { busy, error, run } = useAction();
  const base = toBaseline(project);
  const [value, setValue] = useState(String(initial ?? Math.min(95, (base?.right ?? 70) + 5)));
  const target = targetFromOutOf100(Number(value));
  return (
    <Card variant="violet" aria-label="Pick your target" className="gap-3 p-4">
      <h2 className="text-base font-semibold leading-[normal] text-ink">Pick your target</h2>
      <p className="text-sm leading-5 text-ink-2">
        {intro ??
          "How many predictions out of 100 do you want to be right? I will run a small free pilot and give an estimate of the chance a full run gets there. It is an estimate, not a promise."}
      </p>
      <div className="max-w-[220px]">
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
      <div>
        <Button
          size="md"
          disabled={busy || target === null}
          onClick={() =>
            run(async () => {
              await real.runPilot(project.id, target as number);
              await onChanged();
            })
          }
        >
          {busy ? "Running the free pilot (about half a minute)…" : "Run the free pilot"}
        </Button>
      </div>
      <ErrorLine message={error} />
    </Card>
  );
}
