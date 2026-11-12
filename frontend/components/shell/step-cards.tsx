"use client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EstimateNote } from "@/components/ui/estimate-note";
import { Tag } from "@/components/ui/tag";
import { toBaseline, toFindings, toForecast, type ForecastView } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import * as real from "@/lib/api-real";
import { AXIS_TICKS, barPercent } from "@/lib/chart-scale";
import type { MoneySummary } from "@/lib/money-summary";
import { cn } from "@/lib/utils";
import { FixPanel } from "./fix-panel";
import { ErrorLine, Row, useAction } from "./step-parts";

// Result cards of the free steps, in plain words. They read the project (server state), never the chat text.

export function DatasetCard({ project }: { project: BProject }) {
  const d = project.dataset;
  if (!d) return null;
  return (
    <Card aria-label="Your data" className="gap-2.5 p-4">
      <h2 className="text-section text-ink">Your data</h2>
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
    <Card aria-label="Data check" data-testid="readiness-card" className="gap-3 p-4">
      <div className="flex items-center gap-4">
        <div className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-brand text-title text-on-brand">{r.grade}</div>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5 text-body">
          <h2 className="text-section text-ink">Data check: grade {r.grade}</h2>
          <p className="text-muted">How ready your data is. A guide, not a promise.</p>
        </div>
      </div>
      <ul className="flex flex-col gap-1.5 text-body">
        {findings.map((f, i) => (
          <li key={i} className="flex gap-2">
            <Tag variant={f.ok ? "success" : "warning"} className="shrink-0">
              {f.ok ? "OK" : "NOTE"}
            </Tag>
            <span className="text-ink-2">{f.text}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

interface BarSpec {
  value: number;
  label: string;
  className: string;
}

// Bars on a fixed 0 to 100 scale with an axis, so heights are proportional. Values are the server's, out of 100.
export function ScoreChart({ bars }: { bars: BarSpec[] }) {
  return (
    <figure
      className="flex shrink-0 flex-col gap-1.5"
      role="img"
      aria-label={bars.map((b) => `${b.label}: ${b.value} out of 100`).join(". ")}
    >
      <div className="flex gap-2">
        <div aria-hidden className="relative h-40 w-7 text-micro text-muted tabular-nums">
          {AXIS_TICKS.map((t) => (
            <span key={t} className="absolute right-0 translate-y-1/2 leading-none" style={{ bottom: `${t}%` }}>
              {t}
            </span>
          ))}
        </div>
        <div aria-hidden className="relative h-40 flex-1 border-b border-border">
          {AXIS_TICKS.filter((t) => t > 0).map((t) => (
            <div key={t} className="absolute inset-x-0 border-t border-border" style={{ bottom: `${t}%` }} />
          ))}
          <div className="absolute inset-0 flex items-end justify-around gap-4 px-3">
            {bars.map((b) => (
              <div key={b.label} className={cn("w-12 rounded-t-md", b.className)} style={{ height: `${barPercent(b.value)}%` }} />
            ))}
          </div>
        </div>
      </div>
      <div className="flex gap-2 text-center text-micro text-muted">
        <span aria-hidden className="w-7 shrink-0" />
        <div className="flex flex-1 justify-around gap-4 px-3">
          {bars.map((b) => (
            <div key={b.label} className="flex w-20 flex-col">
              <span className="text-small font-semibold text-ink tabular-nums">{b.value} out of 100</span>
              <span>{b.label}</span>
            </div>
          ))}
        </div>
      </div>
    </figure>
  );
}

export function FreeTestCard({ project }: { project: BProject }) {
  const plain = project.baseline?.plain;
  if (plain) {
    // A number, a forecast, groups or unusual records: the server's own words, no "out of 100 right".
    return (
      <Card aria-label="Free test" data-testid="baseline-result" className="gap-3 p-4">
        <h2 className="text-section text-ink">Free test</h2>
        <p className="text-body text-ink-2">
          On rows it had not seen, {plain.result}. Compare: {plain.guess}.
        </p>
        {project.trust_level && <p className="text-body text-muted">How much to trust this so far: {project.trust_level}</p>}
      </Card>
    );
  }
  const b = toBaseline(project);
  if (!b || b.right === null || b.guess === null) return null;
  return (
    <Card aria-label="Free test" data-testid="baseline-result" className="gap-3 p-4">
      <h2 className="text-section text-ink">Free test</h2>
      <div className="flex flex-col gap-4">
        <p className="min-w-0 flex-1 text-body text-ink-2">
          On data it had not seen, a simple first model got about <strong>{b.right} out of 100</strong> right. Always
          guessing the most common answer would get about {b.guess} out of 100.{" "}
          {b.beatsGuess ? "So the data does carry a signal." : "So it is not clearly better than a simple guess."}
        </p>
        <ScoreChart
          bars={[
            { value: b.right, label: "First model", className: "bg-bar-baseline" },
            { value: b.guess, label: "Simple guess", className: "bg-bar-target" },
          ]}
        />
      </div>
      {project.trust_level && <p className="text-body text-muted">How much to trust this so far: {project.trust_level}</p>}
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

// Cap / Held / Charged. Values are built by lib/money-summary.ts from server figures; unknown ones read "Not yet".
export function MoneyTriplet({ summary }: { summary: MoneySummary }) {
  const items = [
    { label: "Cap", value: summary.cap, note: "The most you can ever be charged (the cap)" },
    { label: "Held", value: summary.held, note: "A hold on PayPal, not a charge" },
    { label: "Charged", value: summary.charged, note: "Taken only after the run ends" },
  ];
  return (
    <dl data-testid="money-triplet" aria-label="Cap, held and charged" className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {items.map((i) => (
        <div key={i.label} className="flex min-w-0 flex-col gap-0.5 rounded-lg bg-surface p-3">
          <dt className="text-small text-muted">{i.label}</dt>
          <dd className={cn("text-section tabular-nums", i.value === "Not yet" ? "text-muted" : "text-ink")}>{i.value}</dd>
          <dd className="text-micro text-muted">{i.note}</dd>
        </div>
      ))}
    </dl>
  );
}

// After a data fix and a new pilot: the estimate before and after, side by side. Both are estimates.
function BeforeAfter({ f }: { f: ForecastView }) {
  if (!f.before) return null;
  return (
    <div aria-label="Before and after the data fix" data-testid="fix-before-after" className="flex flex-col gap-1 rounded-lg border border-trace-line bg-grad-trace shadow-card p-3 text-body">
      <p className="font-semibold text-ink">After your data fix</p>
      <p className="text-ink-2">
        Before: about {f.before.expected} out of 100, a {f.before.confidence}% chance of reaching {f.before.target} out of 100.
      </p>
      <p className="text-ink-2">
        Now: about {f.expected} out of 100, a {f.confidence}% chance of reaching {f.target} out of 100.
      </p>
      <EstimateNote />
    </div>
  );
}

// `note` is false where the screen shows its own EstimateNote (the price card).
export function ForecastCard({ f, note = true }: { f: ForecastView; note?: boolean }) {
  if (f.plain) {
    // A number, a forecast, groups or unusual records: words from the server, every one an estimate.
    return (
      <Card aria-label="Forecast (estimate)" data-testid="forecast-card" className="gap-2.5 p-4">
        <h2 className="text-section text-ink">Forecast (estimate)</h2>
        <dl className="flex flex-col gap-1.5">
          <Row label="Your goal" value={f.plain.target_text} />
          <Row label="What we expect (estimate)" value={f.plain.typical_error_text ?? f.plain.steadiness_text ?? ""} />
          <Row label="Likely range (estimate)" value={f.plain.band_text} />
          <Row label="Chance of reaching your goal (estimate)" value={f.plain.confidence_text} />
          {f.modelType && <Row label="Model type tested" value={f.modelType.name} />}
        </dl>
        {f.modelType && <p className="text-micro text-muted">{f.modelType.note}</p>}
        {note && <EstimateNote>From a small free pilot. An estimate, not a promise.</EstimateNote>}
      </Card>
    );
  }
  return (
    <Card aria-label="Forecast (estimate)" data-testid="forecast-card" className="gap-2.5 p-4">
      <h2 className="text-section text-ink">Forecast (estimate)</h2>
      <dl className="flex flex-col gap-1.5">
        <Row label="Your target" value={`${f.target} out of 100`} />
        <Row label="Expected result (estimate)" value={`about ${f.expected} out of 100`} />
        <Row label="Likely range (estimate)" value={`${f.low} to ${f.high} out of 100`} />
        <Row label="Chance of reaching your target (estimate)" value={`about ${f.confidence}%`} />
        {f.modelType && <Row label="Model type tested" value={f.modelType.name} />}
      </dl>
      {f.modelType && <p className="text-micro text-muted">{f.modelType.note}</p>}
      <BeforeAfter f={f} />
      {note && <EstimateNote>From a small free pilot. An estimate, not a promise.</EstimateNote>}
    </Card>
  );
}

// Screen "not eligible": plain reason, the issues behind it, one click to try the suggested target (a free pilot).
export function EligibilityCard({ project, onChanged }: { project: BProject; onChanged: () => void | Promise<void> }) {
  const f = toForecast(project.forecast);
  const { busy, error, run } = useAction();
  if (!f) return null;
  return (
    <Card variant="warning" aria-label="Not eligible for a price yet" data-testid="eligibility-card" className="gap-3 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-section text-ink">We cannot offer a price for this target yet</h2>
        <Tag>Nothing charged</Tag>
      </div>
      <p className="text-body text-ink-2">{f.reason || "The forecast is too uncertain to sell a run."}</p>
      {f.issues.length > 0 && (
        <>
          <h3 className="text-small font-semibold text-ink">What holds the result back</h3>
          <ul className="flex flex-col gap-2.5">
            {f.issues.map((r, i) => (
              <li key={i} className="flex items-center gap-2.5 text-body text-ink">
                <span aria-hidden className="size-2 shrink-0 rounded-full bg-warning" />
                <span className="min-w-0 flex-1">{r}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <BeforeAfter f={f} />
      <p className="text-small text-muted">The pilot is free, so you can try again as often as you like.</p>
      <FixPanel project={project} onChanged={onChanged} />
      {f.suggestedTarget !== null && (project.task_type ?? "classification") === "classification" && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
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
          <Tag variant="brand">Suggested</Tag>
        </div>
      )}
      <ErrorLine message={error} />
    </Card>
  );
}
