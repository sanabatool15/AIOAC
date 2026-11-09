import test from "node:test";
import assert from "node:assert/strict";
import { AXIS_TICKS, barPercent } from "../lib/chart-scale";
import { holdPhase, moneySummary, phaseView, projectMoney } from "../lib/money-summary";

test("projectMoney reads the quote cap and the stored hold; a fresh quote ignores an old hold", () => {
  const p = { quote: { cap_cents: 700 }, payment: { state: "held", hold_cents: 700 } };
  assert.equal(projectMoney(p).held, "$7.00");
  assert.equal(projectMoney(p, false).held, "Not yet");
  assert.equal(projectMoney({ quote: null, payment: null }).cap, "Not yet");
});

test("waiting for approval: cap known, nothing held or charged yet", () => {
  const m = moneySummary(700, { state: "none", hold_cents: 700 });
  assert.deepEqual([m.cap, m.held, m.charged, m.phase], ["$7.00", "Not yet", "Not yet", "waiting"]);
});

test("no payment yet: only the quote cap is known", () => {
  const m = moneySummary(700, null);
  assert.deepEqual([m.cap, m.held, m.charged], ["$7.00", "Not yet", "Not yet"]);
  assert.equal(moneySummary(null, null).cap, "Not yet");
});

test("hold approved: held shown, still nothing charged", () => {
  const m = moneySummary(700, { state: "held", hold_cents: 700 });
  assert.deepEqual([m.held, m.charged, m.phase], ["$7.00", "Not yet", "approved"]);
});

test("finished: charged comes from the receipt total, unknown total is a dash not a guess", () => {
  assert.equal(moneySummary(700, { state: "fee_captured", hold_cents: 700, total_charged_cents: 123 }).charged, "$1.23");
  assert.equal(moneySummary(700, { state: "released", hold_cents: 700, total_charged_cents: 0 }).charged, "$0.00");
  assert.equal(moneySummary(700, { state: "fee_skipped", hold_cents: 700 }).charged, "—");
});

test("declined, expired and cancelled: nothing was charged", () => {
  for (const s of ["declined", "expired", "voided"]) {
    const m = moneySummary(700, { state: s, hold_cents: 700 });
    assert.equal(m.charged, "$0.00");
    assert.notEqual(m.held, "$7.00");
  }
  assert.equal(holdPhase("voided"), "cancelled");
});

test("every phase has a label and a tone", () => {
  for (const p of ["none", "waiting", "approved", "finished", "declined", "expired", "cancelled"] as const) {
    assert.ok(phaseView(p).label.length > 0);
  }
  assert.equal(phaseView("declined").tone, "danger");
});

test("chart bars are proportional on a 0 to 100 scale", () => {
  assert.equal(barPercent(50), 50);
  assert.equal(barPercent(73.46), 73.5);
  assert.equal(barPercent(-5), 0);
  assert.equal(barPercent(140), 100);
  assert.equal(barPercent(NaN), 0);
  assert.deepEqual([...AXIS_TICKS], [0, 25, 50, 75, 100]);
});
