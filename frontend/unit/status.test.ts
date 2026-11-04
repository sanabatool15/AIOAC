import test from "node:test";
import assert from "node:assert/strict";
import { isSettling, screenFor, stepIndex } from "../lib/status";
import type { BForecast } from "../lib/api";

const forecast = (eligible: boolean) => ({ eligible }) as BForecast;
const p = (status: string, f: BForecast | null = null) => ({ status, forecast: f, quote: null });

test("each backend status picks its screen (specs/api.md B8)", () => {
  assert.equal(screenFor(p("described")), "data");
  assert.equal(screenFor(p("data_chosen")), "readiness");
  assert.equal(screenFor(p("readiness_done")), "baseline");
  assert.equal(screenFor(p("baseline_done")), "target");
  assert.equal(screenFor(p("quoted", forecast(true))), "quote");
  assert.equal(screenFor(p("awaiting_payment")), "pay");
  assert.equal(screenFor(p("paid")), "paid");
  assert.equal(screenFor(p("training")), "training");
  assert.equal(screenFor(p("done")), "result");
  assert.equal(screenFor(p("stopped")), "stopped");
  assert.equal(screenFor(p("voided")), "voided");
  assert.equal(screenFor(p("failed")), "voided");
});

test("a forecast decides between target, not eligible and quote", () => {
  assert.equal(screenFor(p("baseline_done", forecast(false))), "ineligible");
  assert.equal(screenFor(p("baseline_done", forecast(true))), "quote");
  assert.equal(screenFor(p("quoted", forecast(false))), "ineligible");
});

test("unknown or missing status falls to a safe generic screen, never throws", () => {
  assert.equal(screenFor(p("something_new")), "unknown");
  assert.equal(screenFor(null), "unknown");
  assert.equal(screenFor(undefined), "unknown");
  assert.equal(stepIndex("unknown"), 0);
});

test("steps only move forward along the demo path", () => {
  const order = ["data", "readiness", "baseline", "target", "quote", "pay", "training", "result"] as const;
  const idx = order.map(stepIndex);
  assert.deepEqual(idx, [...idx].sort((a, b) => a - b));
});

test("polling is on only while the server is still moving", () => {
  assert.equal(isSettling("training"), true);
  assert.equal(isSettling("failed"), true);
  assert.equal(isSettling("done"), false);
  assert.equal(isSettling(undefined), false);
});
