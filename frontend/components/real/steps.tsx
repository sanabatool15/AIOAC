"use client";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import {
  csvColumns,
  quoteFromProject,
  targetFromOutOf100,
  toBaseline,
  toFindings,
  toForecast,
  type ForecastView,
} from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import * as real from "@/lib/api-real";
import { ErrorLine, Panel, Row, useAction } from "./parts";

interface StepProps {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

// ---- earlier results, shown above the current step ----
export function History({ project }: { project: BProject }) {
  const findings = toFindings(project);
  const baseline = toBaseline(project);
  return (
    <>
      {project.dataset && (
        <Panel title="Your data">
          <dl className="flex flex-col gap-1.5">
            <Row label="Rows" value={project.dataset.rows.toLocaleString()} />
            <Row label="Columns" value={project.dataset.columns} />
            <Row label="We will predict" value={project.dataset.target} />
          </dl>
        </Panel>
      )}
      {project.readiness && (
        <Panel title={`Data check: grade ${project.readiness.grade}`}>
          <ul className="flex flex-col gap-1.5 text-sm">
            {findings.map((f, i) => (
              <li key={i} className="flex gap-2">
                <span className={f.ok ? "font-semibold text-success" : "font-semibold text-muted"}>
                  {f.ok ? "OK" : "NOTE"}
                </span>
                <span className="text-ink-2">{f.text}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {baseline && (
        <Panel title="Free test" variant="violet">
          <p className="text-sm leading-5 text-ink-2">
            On data it had not seen, a simple first model got about{" "}
            <strong>{baseline.right} out of 100</strong> right. Always guessing the most common
            answer would get about {baseline.guess} out of 100.
          </p>
          {project.trust_level && (
            <p className="text-sm text-muted">How much to trust this so far: {project.trust_level}</p>
          )}
        </Panel>
      )}
    </>
  );
}

// ---- 1. data ----
function guessTarget(cols: string[]): string {
  const hint = cols.find((c) => /^(target|label|class|churn|outcome|y)$/i.test(c));
  return hint ?? cols[cols.length - 1] ?? "";
}

export function DataStep({ project, onChanged }: StepProps) {
  const { busy, error, run, setError } = useAction();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ name: string; text: string; cols: string[] } | null>(null);
  const [target, setTarget] = useState("");
  const [candidate, setCandidate] = useState<string | null>(null);

  async function pick(f: File | undefined) {
    setError(null);
    setCandidate(null);
    if (!f) return;
    if (!/\.csv$/i.test(f.name)) return setError("Please choose a CSV file.");
    if (f.size > 20 * 1024 * 1024) return setError("That file is over 20 MB. Please use a smaller one.");
    const text = await f.text();
    const cols = csvColumns(text);
    if (cols.length < 2) return setError("We could not find column names in the first row of that file.");
    setFile({ name: f.name, text, cols });
    setTarget(guessTarget(cols));
  }

  return (
    <Panel title="Add your data">
      <p className="text-sm leading-5 text-ink-2">
        Goal: {project.goal}. Upload a CSV file (a table with a row per case and a header row), then
        tell us which column holds the answer you want predicted.
      </p>
      <input
        ref={fileRef}
        type="file"
        accept=".csv,text/csv"
        aria-label="CSV file"
        className="text-sm"
        onChange={(e) => void pick(e.target.files?.[0])}
      />
      {file && (
        <>
          <Field label="Which column should we predict?" htmlFor="target-col">
            <select
              id="target-col"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="w-full rounded-lg border border-border bg-white px-3 py-2.5 text-sm text-ink"
            >
              {file.cols.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <Button
            size="md"
            disabled={busy || !target}
            onClick={() =>
              run(async () => {
                let id = candidate;
                if (!id) {
                  id = (await real.uploadCsv(project.id, file.name, file.text)).candidate_id;
                  setCandidate(id);
                }
                await real.selectDataset(project.id, id, target);
                await onChanged();
              })
            }
          >
            {busy ? "Saving your data…" : "Use this data"}
          </Button>
        </>
      )}
      <ErrorLine message={error} />
    </Panel>
  );
}

// ---- 2. readiness ----
export function ReadinessStep({ project, onChanged }: StepProps) {
  const { busy, error, run } = useAction();
  return (
    <Panel title="Check your data">
      <p className="text-sm leading-5 text-ink-2">
        I will look for missing values, copies and other problems, and give your data a grade. This is
        free.
      </p>
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
      <ErrorLine message={error} />
    </Panel>
  );
}

// ---- 3. free test ----
export function BaselineStep({ project, onChanged }: StepProps) {
  const { busy, error, run } = useAction();
  return (
    <Panel title="Run the free test">
      <p className="text-sm leading-5 text-ink-2">
        I will train a small first model here, at no cost, and test it on rows it has not seen. It
        gives an honest first signal. It is not a promise of the final result.
      </p>
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
      <ErrorLine message={error} />
    </Panel>
  );
}

// ---- 4a. target + free pilot ----
export function TargetForm({
  project,
  onChanged,
  initial,
  intro,
}: StepProps & { initial?: number | null; intro?: string }) {
  const { busy, error, run } = useAction();
  const base = toBaseline(project);
  const [value, setValue] = useState(String(initial ?? Math.min(95, (base?.right ?? 70) + 5)));
  const target = targetFromOutOf100(Number(value));
  return (
    <Panel title="Pick your target">
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
      <ErrorLine message={error} />
    </Panel>
  );
}

export function ForecastCard({ f }: { f: ForecastView }) {
  return (
    <Panel title="Forecast (estimate)" variant="blue">
      <dl className="flex flex-col gap-1.5">
        <Row label="Your target" value={`${f.target} out of 100`} />
        <Row label="Expected result (estimate)" value={`about ${f.expected} out of 100`} />
        <Row label="Likely range (estimate)" value={`${f.low} to ${f.high} out of 100`} />
        <Row label="Chance of reaching your target (estimate)" value={`about ${f.confidence}%`} />
      </dl>
    </Panel>
  );
}

// ---- 4b. not eligible ----
export function IneligibleStep({ project, onChanged }: StepProps) {
  const f = toForecast(project.forecast);
  const { busy, error, run } = useAction();
  if (!f) return null;
  return (
    <>
      <Panel title="We cannot sell this run yet" variant="amber">
        <p className="text-sm leading-5 text-ink-2">{f.reason || "The forecast is too uncertain to sell a run."}</p>
        {f.issues.length > 0 && (
          <ul className="list-disc pl-5 text-sm text-ink-2">
            {f.issues.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        )}
        <p className="text-sm text-muted">Nothing was charged. The pilot is free.</p>
        {f.suggestedTarget !== null && (
          <Button
            size="md"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await real.runPilot(project.id, (f.suggestedTarget as number) / 100);
                await onChanged();
              })
            }
          >
            {busy ? "Running the free pilot…" : `Try ${f.suggestedTarget} out of 100 instead (free)`}
          </Button>
        )}
        <ErrorLine message={error} />
      </Panel>
      <TargetForm project={project} onChanged={onChanged} initial={f.suggestedTarget} intro="Or choose a lower target of your own. Another pilot is free." />
    </>
  );
}

// ---- 5. quote ----
export function QuoteStep({ project, onChanged }: StepProps) {
  const f = toForecast(project.forecast);
  // Only a quote made for this round counts; after an Improve pilot the old quote is stale.
  const q = project.status === "quoted" ? quoteFromProject(project) : null;
  const { busy, error, run } = useAction();
  const requote = (
    <Button
      variant="outline"
      size="md"
      disabled={busy}
      onClick={() =>
        run(async () => {
          await real.createQuote(project.id);
          await onChanged();
        })
      }
    >
      {q ? "Get a new price" : busy ? "Working out the price…" : "Get my price"}
    </Button>
  );
  return (
    <>
      {f && <ForecastCard f={f} />}
      {!q ? (
        <Panel title="Your price">
          <p className="text-sm leading-5 text-ink-2">
            The pilot looks good enough to offer a run. I will work out one price for the full run.
          </p>
          <div>{requote}</div>
          <ErrorLine message={error} />
        </Panel>
      ) : (
        <Panel title="Your price (estimate)" variant="peach">
          <dl className="flex flex-col gap-1.5">
            <Row label="Estimated total" value={q.estimate} strong />
            <Row label="Likely range (estimate)" value={q.range} />
            <Row label="Most you can ever be charged (the cap)" value={q.cap} strong />
            <Row label="Compute, up to" value={q.computeMax} />
            <Row label="Success fee, up to (only if verified)" value={q.feeMax} />
          </dl>
          <p className="text-sm leading-5 text-ink-2">
            You pay compute either way. The success fee only if the target is verified on data the model
            never saw. PayPal holds the cap but charges nothing until the run is done; anything unused is
            released. This is PayPal sandbox test money only.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="md"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const url = await real.startPayment(project.id);
                  window.location.assign(url);
                })
              }
            >
              {busy ? "Opening PayPal…" : "Approve and hold with PayPal"}
            </Button>
            {requote}
          </div>
          <ErrorLine message={error} />
        </Panel>
      )}
    </>
  );
}

// ---- 6. pay (awaiting_payment) ----
export function PayStep({ project, onChanged }: StepProps) {
  const router = useRouter();
  const { busy, error, run } = useAction();
  const pay = project.payment;
  const dead = pay && ["declined", "expired", "voided"].includes(pay.state);
  const q = quoteFromProject(project);
  return (
    <Panel title="Waiting for your PayPal approval" variant="peach">
      {dead ? (
        <p className="text-sm leading-5 text-ink-2">
          That PayPal hold did not go through ({pay?.state}). Nothing was charged. Get a new price to
          try again.
        </p>
      ) : (
        <p className="text-sm leading-5 text-ink-2">
          PayPal will hold up to {q?.cap ?? "the cap"} and charge nothing yet. Approve it on PayPal, then
          come back here. If you already approved it, press &quot;Check my approval&quot;.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {dead ? (
          <Button
            size="md"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await real.createQuote(project.id);
                await onChanged();
              })
            }
          >
            Get a new price
          </Button>
        ) : (
          <>
            <Button
              size="md"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const url = await real.startPayment(project.id);
                  window.location.assign(url);
                })
              }
            >
              Open PayPal
            </Button>
            <Button
              variant="outline"
              size="md"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  if (pay) real.rememberPayment({ paymentId: pay.payment_id, projectId: project.id });
                  router.push("/pay/return");
                })
              }
            >
              Check my approval
            </Button>
          </>
        )}
      </div>
      <ErrorLine message={error} />
    </Panel>
  );
}
