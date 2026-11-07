import test from "node:test";
import assert from "node:assert/strict";
import {
  csvColumns,
  dollars,
  outOf100,
  percent,
  quoteFromProject,
  targetFromOutOf100,
  toBaseline,
  toFindings,
  toForecast,
  toQuote,
  toReceipt,
  toTraining,
} from "../lib/adapters";
import type { BProject, BQuote, BReceipt, BTraining, BForecast } from "../lib/api";
import {
  fx,
  projectQuoted,
  receiptMissed,
  trainingDoneMissed,
  trainingNotStarted,
  trainingRunning,
} from "./fixtures";

test("dollars converts whole cents and is null-safe", () => {
  assert.equal(dollars(56), "$0.56");
  assert.equal(dollars(700), "$7.00");
  assert.equal(dollars(0), "$0.00");
  assert.equal(dollars(null), "—");
  assert.equal(dollars(undefined), "—");
  assert.equal(dollars(Number.NaN), "—");
});

test("fractions become whole percents and 'N out of 100'", () => {
  assert.equal(percent(0.7291), 73);
  assert.equal(percent(null), null);
  assert.equal(outOf100(0.8), "80 out of 100");
  assert.equal(outOf100(undefined), "—");
});

test("target input maps to a 0-1 fraction only inside 1..99", () => {
  assert.equal(targetFromOutOf100(80), 0.8);
  assert.equal(targetFromOutOf100(0), null);
  assert.equal(targetFromOutOf100(100), null);
  assert.equal(targetFromOutOf100(Number.NaN), null);
});

test("project before anything exists: every adapter returns null or empty, never throws", () => {
  const p = fx.projectNew as unknown as BProject;
  assert.deepEqual(toFindings(p), []);
  assert.equal(toBaseline(p), null);
  assert.equal(toForecast(p.forecast), null);
  assert.equal(quoteFromProject(p), null);
  assert.equal(toReceipt(null), null);
  assert.equal(toTraining(null), null);
});

test("baseline and findings from the real project shape", () => {
  const p = projectQuoted as unknown as BProject;
  assert.deepEqual(toBaseline(p), { right: 73, guess: 74, beatsGuess: false });
  assert.deepEqual(toFindings(p), [
    { ok: true, text: "Enough rows to train a useful model" },
    { ok: false, text: "5 duplicate rows found (removed automatically)" },
  ]);
});

test("forecast: not eligible keeps the plain reason, issues and suggested target", () => {
  const f = toForecast(fx.forecastIneligible as unknown as BForecast)!;
  assert.equal(f.eligible, false);
  assert.equal(f.target, 80);
  assert.equal(f.confidence, 39);
  assert.equal(f.suggestedTarget, 76);
  assert.match(f.reason, /not enough to sell you a run/);
  assert.equal(f.issues.length, 2);
  const ok = toForecast(fx.forecastOk as unknown as BForecast)!;
  assert.equal(ok.eligible, true);
  assert.equal(ok.reason, "");
  assert.equal(ok.suggestedTarget, null);
});

test("quote: cents to dollars, the cap is a fact, terms pass through", () => {
  const q = toQuote(fx.quote as unknown as BQuote)!;
  assert.equal(q.estimate, "$0.56");
  assert.equal(q.range, "$0.55 to $0.56");
  assert.equal(q.cap, "$0.56");
  assert.equal(q.computeMax, "$0.53");
  assert.equal(q.feeMax, "$0.03");
  assert.equal(q.target, 70);
  assert.match(q.terms, /compute either way/);
  const thin = quoteFromProject(projectQuoted as unknown as BProject)!;
  assert.equal(thin.cap, "$0.56");
  assert.equal(thin.computeMax, "$0.53");
});

test("model type: shown in plain words with the not-a-promise note; missing for old quotes", () => {
  const withType = {
    ...(fx.quote as unknown as BQuote),
    model_type: { family: "boosting", name: "a boosted-trees model", note: "This is only the model type we tested, not a promise of a better result." },
  };
  const q = toQuote(withType)!;
  assert.equal(q.modelType?.name, "a boosted-trees model");
  assert.match(q.modelType!.note, /not a promise/);
  assert.equal(toQuote(fx.quote as unknown as BQuote)!.modelType, null);
  const f = toForecast({ ...(fx.forecastOk as unknown as BForecast), model_type: withType.model_type })!;
  assert.equal(f.modelType?.name, "a boosted-trees model");
  assert.equal(toForecast(fx.forecastOk as unknown as BForecast)!.modelType, null);
});

test("training: not_started is normal; running and done map cleanly", () => {
  const ns = toTraining(trainingNotStarted as unknown as BTraining)!;
  assert.equal(ns.status, "not_started");
  assert.equal(ns.progress, 0);
  assert.equal(ns.eta, null);
  const run = toTraining(trainingRunning as unknown as BTraining)!;
  assert.equal(run.progress, 50);
  assert.equal(run.spend, "$0.12");
  assert.equal(run.eta, "30 sec to 3 min");
  const done = toTraining(trainingDoneMissed as unknown as BTraining)!;
  assert.equal(done.passed, false);
  assert.deepEqual(done.verified, { value: 72, target: 80 });
});

test("receipt: compute only when the target was missed", () => {
  const r = toReceipt(receiptMissed as unknown as BReceipt)!;
  assert.equal(r.held, "$0.56");
  assert.equal(r.compute, "$0.40");
  assert.equal(r.fee, "$0.00");
  assert.equal(r.released, "$0.16");
  assert.equal(r.total, "$0.40");
});

test("csvColumns reads the header row, with quotes and a BOM", () => {
  assert.deepEqual(csvColumns("tenure,monthly,contract,churn\n1,2,3,4"), [
    "tenure",
    "monthly",
    "contract",
    "churn",
  ]);
  assert.deepEqual(csvColumns('﻿"a, b",c\r\n1,2'), ["a, b", "c"]);
  assert.deepEqual(csvColumns(""), []);
});
