import test from "node:test";
import assert from "node:assert/strict";
import { formatWhen, overviewLine, paymentStateLabel, runStatusLabel, toActivity, toHistory } from "../lib/screens";
import type { BActivityItem, BHistory } from "../lib/api";
import { sx } from "./fixtures-screens";

const history = sx.history as unknown as BHistory;

test("formatWhen reads a zone-less server time as UTC and tolerates junk", () => {
  assert.equal(formatWhen("2026-11-06T17:13:05.323855", "UTC"), "Nov 6, 17:13");
  assert.equal(formatWhen("2026-11-06T17:13:06.699071+00:00", "UTC"), "Nov 6, 17:13");
  assert.equal(formatWhen(null), "");
  assert.equal(formatWhen("not a date"), "");
});

test("payment states are said in plain words", () => {
  assert.equal(paymentStateLabel("released", 0), "Nothing charged, hold released");
  assert.equal(paymentStateLabel("released", 12), "Finished: the rest was released");
  assert.equal(paymentStateLabel("fee_skipped"), "Finished: compute only, no success fee");
  assert.equal(paymentStateLabel("voided"), "Cancelled, nothing charged");
  assert.equal(paymentStateLabel("weird_state"), "weird state");
});

test("run statuses", () => {
  assert.equal(runStatusLabel("done"), "Finished");
  assert.equal(runStatusLabel("stopped"), "Stopped by you");
});

test("history from the real body: dollars, out of 100, no raw ids as text", () => {
  const v = toHistory(history);
  assert.equal(v.versions.length, 1);
  assert.match(v.versions[0].detail, /1,500 rows, 5 columns, predicting "left"/);
  assert.match(v.runs[0].result, /about 85 out of 100 right, target 70 out of 100\. Target reached\./);
  assert.equal(v.runs[0].passed, true);
  assert.equal(v.runs[0].cost, "$0.00");
  assert.equal(v.quotes[0].estimate, "$0.56");
  assert.equal(v.quotes[0].range, "$0.55 to $0.56");
  assert.equal(v.payment?.held, "$0.56");
  assert.equal(v.payment?.state, "Nothing charged, hold released");
  assert.equal(v.payment?.released, "$0.56");
});

test("history of a new project is empty and well formed", () => {
  const v = toHistory({ versions: [], runs: [], quotes: [], payment: null });
  assert.deepEqual(v, { versions: [], runs: [], quotes: [], payment: null });
  assert.deepEqual(toHistory(null).runs, []);
});

test("a run with no verification still reads honestly", () => {
  const h = { ...history, runs: [{ ...history.runs[0], result: { accuracy: 0.8 } }] } as BHistory;
  assert.match(toHistory(h).runs[0].result, /About 80 out of 100 right \(an estimate\)/);
  const none = { ...history, runs: [{ ...history.runs[0], result: null }] } as BHistory;
  assert.equal(toHistory(none).runs[0].result, "No result saved.");
});

test("activity keeps the server sentences and adds a time", () => {
  const a = toActivity(sx.activity as unknown as BActivityItem[]);
  assert.equal(a.length, 12);
  assert.equal(a[0].text, 'You said: "Which subscription customers will leave?"');
  assert.ok(a[0].when.length > 0);
  assert.equal(new Set(a.map((x) => x.key)).size, 12);
  assert.deepEqual(toActivity(undefined), []);
});

test("overview line covers every status", () => {
  for (const s of ["described", "data_chosen", "readiness_done", "baseline_done", "quoted", "awaiting_payment", "paid", "training", "done", "stopped", "voided", "failed"])
    assert.ok(overviewLine(s).length > 10, s);
  assert.equal(overviewLine("???"), "");
});
