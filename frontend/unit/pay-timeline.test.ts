import test from "node:test";
import assert from "node:assert/strict";
import { payPill, payTimeline } from "../lib/pay-timeline";

const quote = { id: "q", estimate_cents: 200, low_cents: 150, high_cents: 300, cap_cents: 500, success_fee_max_cents: 50, approved: false };

test("pill: no price, price ready, held, finished", () => {
  assert.equal(payPill({ status: "described", quote: null, payment: null }).label, "Payment");
  assert.deepEqual(payPill({ status: "quoted", quote, payment: null }), { label: "Pay up to $5.00", tone: "primary" });
  assert.equal(payPill({ status: "training", quote, payment: { payment_id: "p", state: "held", approve_url: null, hold_cents: 500 } }).label, "Held $5.00");
  assert.equal(payPill({ status: "done", quote, payment: { payment_id: "p", state: "fee_captured", approve_url: null, hold_cents: 500 } }).tone, "ok");
});

test("timeline: a quoted chat waits on the hold", () => {
  const t = payTimeline({ status: "quoted", quote, payment: null }, null);
  assert.deepEqual(t.map((s) => s.state), ["done", "current", "todo", "todo", "todo"]);
});

test("timeline: a released hold ends the story with nothing charged", () => {
  const receipt = { payment_id: "p", state: "released", hold_cents: 500, compute_captured_cents: 0, fee_captured_cents: 0, released_cents: 500, total_charged_cents: 0 };
  const t = payTimeline({ status: "done", quote, payment: { payment_id: "p", state: "released", approve_url: null, hold_cents: 500 } }, receipt);
  assert.equal(t[4].state, "done");
  assert.match(t[4].detail, /Target missed/);
});
