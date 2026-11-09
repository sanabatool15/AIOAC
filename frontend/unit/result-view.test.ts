import test from "node:test";
import assert from "node:assert/strict";
import { toTraining } from "../lib/adapters";
import type { BReceipt, BTraining } from "../lib/api";
import { needsSettleRetry, OUR_FAILURE_TEXT, recapNote, toRecap, toResultView } from "../lib/result-view";
import {
  receiptMissed,
  receiptPendingSettle,
  receiptVerified,
  trainingDoneMissed,
  trainingDoneVerified,
  trainingFailed,
  trainingRunning,
  trainingStopped,
} from "./fixtures";

const T = (x: unknown) => x as BTraining;
const R = (x: unknown) => x as BReceipt;

test("verified: passed is true, shows value and target out of 100, compute plus fee", () => {
  const v = toResultView(T(trainingDoneVerified));
  assert.equal(v.kind, "verified");
  assert.equal(v.value, 84);
  assert.equal(v.target, 80);
  assert.match(v.body, /84 out of 100/);
  assert.match(v.body, /80 out of 100/);
});

test("missed: compute only, no success fee, never 'pay $0'", () => {
  const v = toResultView(T(trainingDoneMissed));
  assert.equal(v.kind, "missed");
  assert.equal(v.value, 72);
  assert.match(v.body, /You paid for compute only, no success fee/);
  assert.doesNotMatch(v.body, /\$0/);
});

test("no verification block gives a neutral result", () => {
  assert.equal(toResultView(T(trainingRunning)).kind, "unchecked");
  assert.equal(toResultView(null).kind, "unchecked");
});

test("money recap from the receipt: held, charged, released in dollars", () => {
  const r = toRecap(R(receiptMissed))!;
  assert.deepEqual([r.held, r.compute, r.fee, r.released, r.charged], ["$0.56", "$0.40", "$0.00", "$0.16", "$0.40"]);
  const ok = toRecap(R(receiptVerified))!;
  assert.deepEqual([ok.compute, ok.fee, ok.charged, ok.released], ["$0.40", "$0.02", "$0.42", "$0.14"]);
  // held = charged + released on a finished hold
  assert.equal(ok.heldCents, ok.chargedCents + ok.releasedCents);
  assert.equal(r.heldCents, r.chargedCents + r.releasedCents);
  assert.equal(toRecap(null), null);
});

test("settle retry shows only while the payment is not in a final state", () => {
  assert.equal(needsSettleRetry(R(receiptPendingSettle)), true);
  assert.equal(needsSettleRetry(R(receiptMissed)), false);
  assert.equal(needsSettleRetry({ state: "voided" }), false);
  assert.equal(needsSettleRetry(null), false);
});

test("stopped and failed training answers map to their own flags", () => {
  assert.equal(toTraining(T(trainingStopped))?.stoppedByUser, true);
  assert.equal(toTraining(T(trainingFailed))?.error, "training failed");
});

test("our-failure text is the agreed wording", () => {
  assert.equal(OUR_FAILURE_TEXT, "Something went wrong on our side. You pay $0. The whole hold was released.");
});

test("recap note never claims a charge that did not happen", () => {
  const zero = toRecap(R({ ...receiptMissed, compute_captured_cents: 0, total_charged_cents: 0, released_cents: 56 }));
  assert.match(recapNote("verified", zero), /Nothing was charged/);
  assert.match(recapNote("verified", toRecap(R(receiptVerified))), /Compute plus the success fee/);
  assert.match(recapNote("missed", toRecap(R(receiptMissed))), /compute only, no success fee/);
});

import { improveStart } from "../lib/result-view";

test("Improve starts at the suggested target, else the current target, never the lower verified result", () => {
  assert.equal(improveStart(0.75, 80), 75);
  assert.equal(improveStart(null, 80), 80);
  assert.equal(improveStart(undefined, 80), 80);
  assert.equal(improveStart(undefined, null), null);
});

import { higherStart, isHigherTarget } from "../lib/result-view";

test("Try a higher target starts a few points above the reached target and never above 99", () => {
  assert.equal(higherStart(94), 97);
  assert.equal(higherStart(98), 99);
  assert.equal(higherStart(99), 99);
  assert.equal(higherStart(null), null);
});

test("a new round after a hit needs a strictly higher target", () => {
  assert.equal(isHigherTarget(99, 94), true);
  assert.equal(isHigherTarget(94, 94), false);
  assert.equal(isHigherTarget(80, 94), false);
  assert.equal(isHigherTarget(null, 94), false);
  assert.equal(isHigherTarget(90, null), true);
});
