// Pure view rules for the end of a run (no React, no fetch): verified or missed, the money recap, the settle retry.
// Inputs are the raw bodies of GET /projects/{id}/training and GET /projects/{id}/payment (specs/api.md A2, A5).
import { dollars, percent, toReceipt } from "./adapters";
import type { BReceipt, BTraining } from "./api";

export type ResultKind = "verified" | "missed" | "unchecked";

export interface ResultView {
  kind: ResultKind;
  value: number | null; // out of 100
  target: number | null; // out of 100
  title: string;
  body: string;
}

const FINAL_PAYMENT_STATES = ["released", "voided", "expired", "declined"];

// verification.passed decides. Never "pay $0 if missed": a miss still pays for compute (payments.md section 1, rule 5).
export function toResultView(t: BTraining | null | undefined): ResultView {
  const v = t?.result?.verification;
  if (!v) {
    return {
      kind: "unchecked",
      value: null,
      target: null,
      title: "Run finished",
      body: "The run is finished. Details are in the receipt below.",
    };
  }
  const value = percent(v.value);
  const target = percent(v.target);
  const checked = `Checked once on test data we kept aside: about ${value} out of 100 right, `;
  if (v.passed === true) {
    return {
      kind: "verified",
      value,
      target,
      title: "Target reached",
      body: `${checked}against your target of ${target} out of 100.`,
    };
  }
  return {
    kind: "missed",
    value,
    target,
    title: "Target not reached",
    body: `${checked}below your target of ${target} out of 100. You paid for compute only, no success fee. We kept the best model.`,
  };
}

export interface Recap {
  held: string;
  charged: string;
  released: string;
  compute: string;
  fee: string;
  chargedCents: number;
  heldCents: number;
  releasedCents: number;
}

// Held, charged and released from the receipt, in dollars. charged = compute + fee (as the server totals it).
export function toRecap(r: BReceipt | null | undefined): Recap | null {
  const v = toReceipt(r);
  if (!r || !v) return null;
  return {
    held: dollars(r.hold_cents),
    charged: dollars(r.total_charged_cents),
    released: dollars(r.released_cents),
    compute: v.compute,
    fee: v.fee,
    chargedCents: r.total_charged_cents ?? 0,
    heldCents: r.hold_cents ?? 0,
    releasedCents: r.released_cents ?? 0,
  };
}

// The run is over but the last PayPal step has not finished (a settle_failed trace): a retry is safe to repeat.
export function needsSettleRetry(r: Pick<BReceipt, "state"> | null | undefined): boolean {
  return !!r && !FINAL_PAYMENT_STATES.includes(r.state);
}

export const OUR_FAILURE_TEXT = "Something went wrong on our side. You pay $0. The whole hold was released.";

// The sentence under the money recap. Built from the numbers, so it never claims a charge that did not happen.
export function recapNote(kind: ResultKind, r: Pick<Recap, "chargedCents"> | null): string {
  if (!r) return "";
  if (r.chargedCents === 0) return "Nothing was charged for this run, so the whole hold was released.";
  if (kind === "verified") return "Compute plus the success fee were charged, because the result was verified. The rest of the hold was released.";
  return "You paid for compute only, no success fee. The rest of the hold was released.";
}

// Where the Improve form's target field starts after a miss: the forecast's suggested target when there is one
// (an estimate we can honestly sell), else the target the user already set. Never the lower verified result.
export function improveStart(suggestedFraction: number | null | undefined, currentTarget: number | null): number | null {
  const suggested = percent(suggestedFraction);
  return suggested ?? currentTarget;
}

// "Try a higher target" after a verified run: the form starts a few points above the target already reached, never above 99.
export const HIGHER_STEP = 3;
export function higherStart(reached: number | null): number | null {
  return reached === null ? null : Math.min(99, reached + HIGHER_STEP);
}
// A new round after a hit needs a strictly higher target (the server enforces it; this only explains it early).
export function isHigherTarget(value: number | null, reached: number | null): boolean {
  return value !== null && (reached === null || value > reached);
}
