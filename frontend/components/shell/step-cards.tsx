"use client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { toBaseline, toFindings, toForecast, type ForecastView } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import * as real from "@/lib/api-real";
import { cn } from "@/lib/utils";
import { FixPanel } from "./fix-panel";
import { ErrorLine, Row, useAction } from "./step-parts";

// Result cards of the free steps, in plain words. They read the project (server state), never the chat text.
// Same look as the polished screens: gradient grade tile, bars, tinted cards.

export function DatasetCard({ project }: { project: BProject }) {
  const d = project.dataset;
  if (!d) return null;
  return (
    <Card aria-label="Your data" className="gap-2.5 p-4">
      <h2 className="text-sm font-semibold text-ink">Your data</h2>
      <dl className="flex flex-col gap-1.5">
        <Row label="Rows" value={d.rows.toLocaleString()} />
        <Row label="Columns" value={d.columns} />
        <Row label="We will predict" value={d.target} />
        <Row label="From" value={d.source} />
      </dl>
    </Card>
  );
}

export function ReadinessCard({ project }: { project: BProject }) {
  const r = project.readiness;
  if (!r) return null;
  const findings = toFindings(project);
  return (
    <Card variant="green" aria-label="Data check" data-testid="readiness-card" className="gap-3 p-4 shadow-card-tight">
      <div className="flex items-center gap-4">
        <div className="flex size-[54px] shrink-0 items-center justify-center rounded-xl bg-brand-gradient text-[28px] font-semibold leading-[normal] text-white shadow-glow">
          {r.grade}
        </div>
        <div className="flex min-w-px flex-1 flex-col gap-0.5 text-sm leading-[normal]">
          <p className="font-semibold text-ink">Data check: grade {r.grade}</p>
          <p className="text-muted">A grade for how ready your data is. It is a guide, not a promise.</p>
        </div>
      </div>
      <ul className="flex flex-col gap-1.5 text-sm">
        {findings.map((f, i) => (
          <li key={i} className="flex gap-2">
            <Tag variant={f.ok ? "brand" : "muted"} className="shrink-0">
              {f.ok ? "OK" : "NOTE"}
            </Tag>
            <span className="text-ink-2">{f.text}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const BAR_PX_PER_PCT = 1.0845;

function Bar({ pct, label, className }: { pct: number; label: string; className: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5 leading-[normal]">
      <p className="text-sm font-semibold text-ink">{pct} out of 100</p>
      <div role="img" aria-label={`${label}: ${pct} out of 100`} className={cn("w-[52px] rounded-md", className)} style={{ height: Math.round(pct * BAR_PX_PER_PCT) }} />
      <p className="text-xs text-muted">{label}</p>
    </div>
  );
}

export function FreeTestCard({ project }: { project: BProject }) {
  const b = toBaseline(project);
  if (!b || b.right === null || b.guess === null) return null;
  return (
    <Card variant="blue" aria-label="Free test" data-testid="baseline-result" className="gap-3 p-[18px] shadow-card-tight">
      <p className="text-sm font-semibold leading-[normal] text-ink">Free test</p>
      <div className="flex items-center gap-7">
        <p className="min-w-px flex-1 text-sm leading-5 text-ink-2">
          On data it had not seen, a simple first model got about <strong>{b.right} out of 100</strong> right. Always
          guessing the most common answer would get about {b.guess} out of 100.{" "}
          {b.beatsGuess ? "So the data does carry a signal." : "So it is not clearly better than a simple guess."}
        </p>
        <div className="flex items-end gap-[22px] pt-1.5">
          <Bar pct={b.right} label="First model" className="bg-bar-baseline" />
          <Bar pct={b.guess} label="Simple guess" className="bg-bar-target" />
        </div>
      </div>
      {project.trust_level && <p className="text-sm text-muted">How much to trust this so far: {project.trust_level}</p>}
      <p className="text-xs text-muted">A first signal on a small test. It is not a promise of the final result.</p>
    </Card>
  );
}

// Everything done so far, above the current step.
export function History({ project }: { project: BProject }) {
  return (
    <>
      <DatasetCard project={project} />
      <ReadinessCard project={project} />
      <FreeTestCard project={project} />
    </>
  );
}

// After a data fix and a new pilot: the estimate before and after, side by side. Both are estimates.
function BeforeAfter({ f }: { f: ForecastView }) {
  if (!f.before) return null;
  return (
    <div aria-label="Before and after the data fix" data-testid="fix-before-after" className="flex flex-col gap-1 rounded-lg border border-border bg-white p-3 text-sm">
      <p className="font-semibold text-ink">After your data fix</p>
      <p className="text-ink-2">
        Before: about {f.before.expected} out of 100, a {f.before.confidence}% chance of reaching {f.before.target} out of 100 (estimate).
      </p>
      <p className="text-ink-2">
        Now: about {f.expected} out of 100, a {f.confidence}% chance of reaching {f.target} out of 100 (estimate).
      </p>
      <p className="text-xs text-muted">We tested whether the fix changes the estimate. It is a small free test, not a promise.</p>
    </div>
  );
}

export function ForecastCard({ f }: { f: ForecastView }) {
  return (
    <Card variant="blue" aria-label="Forecast (estimate)" data-testid="forecast-card" className="gap-2.5 p-4 shadow-card-tight">
      <h2 className="text-sm font-semibold text-ink">Forecast (estimate)</h2>
      <dl className="flex flex-col gap-1.5">
        <Row label="Your target" value={`${f.target} out of 100`} />
        <Row label="Expected result (estimate)" value={`about ${f.expected} out of 100`} />
        <Row label="Likely range (estimate)" value={`${f.low} to ${f.high} out of 100`} />
        <Row label="Chance of reaching your target (estimate)" value={`about ${f.confidence}%`} />
        {f.modelType && <Row label="Model type tested" value={f.modelType.name} />}
      </dl>
      {f.modelType && <p className="text-xs text-muted">{f.modelType.note}</p>}
      <BeforeAfter f={f} />
      <p className="text-xs text-muted">An estimate from a small free pilot, not a promise.</p>
    </Card>
  );
}

// Screen "not eligible": plain reason, the issues behind it, one click to try the suggested target (a free pilot).
export function EligibilityCard({ project, onChanged }: { project: BProject; onChanged: () => void | Promise<void> }) {
  const f = toForecast(project.forecast);
  const { busy, error, run } = useAction();
  if (!f) return null;
  return (
    <Card variant="amber" aria-label="Not eligible for a price yet" data-testid="eligibility-card" className="gap-3 p-5 shadow-card-tight">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold leading-[normal] text-ink">We cannot offer a price for this target yet</h2>
        <Tag>Nothing charged</Tag>
      </div>
      <p className="text-sm leading-5 text-ink-2">{f.reason || "The forecast is too uncertain to sell a run."}</p>
      {f.issues.length > 0 && (
        <>
          <p className="text-xs font-semibold leading-[normal] text-muted">WHAT HOLDS THE RESULT BACK</p>
          <ul className="flex flex-col gap-2.5">
            {f.issues.map((r, i) => (
              <li key={i} className="flex items-center gap-2.5 text-sm leading-[normal] text-ink">
                <span aria-hidden className="size-2 shrink-0 rounded-full bg-brand-gradient" />
                <span className="min-w-px flex-1">{r}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <BeforeAfter f={f} />
      <p className="text-sm text-muted">The pilot is free, so you can try again as often as you like.</p>
      <FixPanel project={project} onChanged={onChanged} />
      {f.suggestedTarget !== null && (
        <div className="flex flex-wrap items-center gap-3">
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
          <Tag variant="brand">SUGGESTED</Tag>
        </div>
      )}
      <ErrorLine message={error} />
    </Card>
  );
}
