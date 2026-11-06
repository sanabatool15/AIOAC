// The ONE place that converts backend values to what screens show.
// Backend: whole cents, rates 0 to 1, snake_case. Screens: dollars text, "N out of 100", camelCase.
import type {
  BForecast,
  BProject,
  BQuote,
  BReceipt,
  BTraining,
} from "./api";

export type Maybe<T> = T | null | undefined;

// The terms shown with every quote (payments.md section 2, step 4). Fixed text: the money rules are not the server's wording to change on screen.
export const QUOTE_TERMS =
  "You pay for compute either way. The success fee is charged only if the result is verified on test data we keep aside.";

// cents -> "$0.56". Null-safe: a missing amount shows a dash, never "$NaN".
export function dollars(cents: Maybe<number>): string {
  if (cents === null || cents === undefined || !Number.isFinite(cents)) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

// 0.7291 -> 73 (percent as a whole number). Null-safe.
export function percent(fraction: Maybe<number>): number | null {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return null;
  return Math.round(fraction * 100);
}

// 0.73 -> "73 out of 100". The plain-language form of accuracy.
export function outOf100(fraction: Maybe<number>): string {
  const p = percent(fraction);
  return p === null ? "—" : `${p} out of 100`;
}

// Whole number the user typed (1 to 99) -> backend target fraction. null if not usable.
export function targetFromOutOf100(n: number): number | null {
  if (!Number.isFinite(n)) return null;
  const whole = Math.round(n);
  return whole >= 1 && whole <= 99 ? whole / 100 : null;
}

export function duration(seconds: Maybe<number>): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} sec`;
  const m = Math.round(s / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

export interface FindingView {
  ok: boolean;
  text: string;
}
export interface BaselineView {
  right: number | null; // percent
  guess: number | null; // percent
  beatsGuess: boolean;
}
export interface ForecastView {
  target: number | null; // percent
  expected: number | null; // percent (estimate)
  low: number | null;
  high: number | null;
  confidence: number | null; // percent (estimate)
  eligible: boolean;
  reason: string;
  issues: string[];
  suggestedTarget: number | null; // percent
}
export interface QuoteView {
  estimate: string;
  range: string;
  cap: string;
  computeMax: string;
  feeMax: string;
  target: number | null;
  terms: string;
}
export interface ReceiptView {
  state: string;
  held: string;
  compute: string;
  fee: string;
  released: string;
  total: string;
  totalCents: number;
  feeCents: number;
  computeCents: number;
}
export interface TrainingView {
  status: BTraining["status"];
  stage: string;
  progress: number; // 0 to 100
  elapsed: string;
  spend: string;
  cap: string;
  eta: string | null;
  stopRequested: boolean;
  passed: boolean | null;
  verified: { value: number | null; target: number | null } | null;
  error: string | null;
  stoppedByUser: boolean;
}

export function toFindings(p: Maybe<BProject>): FindingView[] {
  return (p?.readiness?.findings ?? []).map((f) => ({
    ok: f.kind === "OK",
    text: f.text,
  }));
}

export function toBaseline(p: Maybe<BProject>): BaselineView | null {
  const b = p?.baseline;
  if (!b) return null;
  const right = percent(b.accuracy);
  const guess = percent(b.simple_guess_accuracy);
  return { right, guess, beatsGuess: right !== null && guess !== null && right > guess };
}

export function toForecast(f: Maybe<BForecast>): ForecastView | null {
  if (!f) return null;
  return {
    target: percent(f.target),
    expected: percent(f.predicted_metric),
    low: percent(f.band_low),
    high: percent(f.band_high),
    confidence: percent(f.confidence),
    eligible: f.eligible === true,
    reason: f.reason ?? "",
    issues: f.issues ?? [],
    suggestedTarget: percent(f.suggested_target),
  };
}

export function toQuote(q: Maybe<BQuote>): QuoteView | null {
  if (!q) return null;
  return {
    estimate: dollars(q.estimate_cents),
    range:
      q.low_cents === q.high_cents
        ? dollars(q.low_cents)
        : `${dollars(q.low_cents)} to ${dollars(q.high_cents)}`,
    cap: dollars(q.cap_cents),
    computeMax: dollars(q.compute_cap_cents),
    feeMax: dollars(q.success_fee_max_cents),
    target: percent(q.target),
    terms: QUOTE_TERMS,
  };
}

// The project read has a thinner quote than POST quote; this builds the parts it can.
export function quoteFromProject(p: Maybe<BProject>): QuoteView | null {
  const q = p?.quote;
  if (!q) return null;
  const f = p?.forecast;
  return {
    estimate: dollars(q.estimate_cents),
    range:
      q.low_cents === q.high_cents
        ? dollars(q.low_cents)
        : `${dollars(q.low_cents)} to ${dollars(q.high_cents)}`,
    cap: dollars(q.cap_cents),
    computeMax: dollars(q.cap_cents - q.success_fee_max_cents),
    feeMax: dollars(q.success_fee_max_cents),
    target: percent(f?.target),
    terms: QUOTE_TERMS,
  };
}

export function toReceipt(r: Maybe<BReceipt>): ReceiptView | null {
  if (!r) return null;
  return {
    state: r.state,
    held: dollars(r.hold_cents),
    compute: dollars(r.compute_captured_cents),
    fee: dollars(r.fee_captured_cents),
    released: dollars(r.released_cents),
    total: dollars(r.total_charged_cents),
    totalCents: r.total_charged_cents ?? 0,
    feeCents: r.fee_captured_cents ?? 0,
    computeCents: r.compute_captured_cents ?? 0,
  };
}

export function toTraining(t: Maybe<BTraining>): TrainingView | null {
  if (!t) return null;
  const v = t.result?.verification;
  const eta = t.eta;
  return {
    status: t.status,
    stage: t.stage ?? "getting ready",
    progress: Math.round(Math.min(1, Math.max(0, t.fraction ?? 0)) * 100),
    elapsed: duration(t.elapsed_seconds),
    spend: dollars(t.spend_so_far_cents ?? 0),
    cap: dollars(t.cap_cents),
    eta: eta ? `${duration(eta.low_seconds)} to ${duration(eta.high_seconds)}` : null,
    stopRequested: t.stop_requested === true,
    passed: v ? v.passed === true : null,
    verified: v ? { value: percent(v.value), target: percent(v.target) } : null,
    error: t.result?.error ?? null,
    stoppedByUser: t.result?.stopped_by_user === true,
  };
}

// First line of a CSV -> column names (simple: handles quotes, no embedded newlines in headers).
export function csvColumns(text: string): string[] {
  const line = text.replace(/^﻿/, "").split(/\r?\n/, 1)[0] ?? "";
  const out: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else quoted = !quoted;
    } else if (ch === "," && !quoted) {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  out.push(cur.trim());
  return out.filter((c) => c.length > 0);
}
