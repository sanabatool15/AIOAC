import test from "node:test";
import assert from "node:assert/strict";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { nextTabId } from "../components/ui/tabs-logic";
import { stepStates, stepSummary } from "../components/ui/stepper-logic";
import { Tabs } from "../components/ui/tabs";
import { Stepper } from "../components/ui/stepper";

const tabs = [
  { id: "history", label: "History" },
  { id: "activity", label: "Activity" },
  { id: "model", label: "Model", disabled: true },
  { id: "share", label: "Share" },
];

test("arrow keys move between tabs, wrap and skip disabled ones", () => {
  assert.equal(nextTabId(tabs, "history", "ArrowRight"), "activity");
  assert.equal(nextTabId(tabs, "activity", "ArrowRight"), "share");
  assert.equal(nextTabId(tabs, "share", "ArrowRight"), "history");
  assert.equal(nextTabId(tabs, "history", "ArrowLeft"), "share");
  assert.equal(nextTabId(tabs, "share", "ArrowLeft"), "activity");
  assert.equal(nextTabId(tabs, "activity", "Home"), "history");
  assert.equal(nextTabId(tabs, "activity", "End"), "share");
  assert.equal(nextTabId(tabs, "activity", "Enter"), null);
  assert.equal(nextTabId([], "x", "ArrowRight"), null);
});

test("tabs render roving tabindex and aria-controls that point at real panels", () => {
  const html = renderToStaticMarkup(h(Tabs, { tabs, value: "activity", onValueChange: () => {}, label: "Project", panels: { history: "H", activity: "A", model: "M", share: "S" } }));
  assert.match(html, /role="tablist"/);
  const buttons = html.match(/<button[^>]*>/g) ?? [];
  assert.equal(buttons.length, 4);
  assert.equal(buttons.filter((b) => b.includes('tabindex="0"')).length, 1);
  assert.ok(buttons.find((b) => b.includes('aria-selected="true"'))?.includes('tabindex="0"'));
  for (const b of buttons) {
    const controls = b.match(/aria-controls="([^"]+)"/)?.[1];
    assert.ok(controls, "every tab has aria-controls");
    assert.ok(html.includes(`id="${controls}"`), "and the panel exists");
  }
  assert.equal((html.match(/hidden=""/g) ?? []).length, 3, "inactive panels are hidden");
});

test("stepper states: done before, current, upcoming after", () => {
  assert.deepEqual(stepStates(4, 1), ["done", "current", "upcoming", "upcoming"]);
  assert.deepEqual(stepStates(3, 3), ["done", "done", "done"]);
  assert.deepEqual(stepStates(2, 0), ["current", "upcoming"]);
  assert.equal(stepSummary(7, 2), "Step 3 of 7");
  assert.equal(stepSummary(7, 99), "Step 7 of 7");
});

test("stepper markup: check on done, aria-current on the current step, compact summary", () => {
  const steps = ["Describe", "Data", "Check", "Price"].map((label) => ({ id: label, label }));
  const html = renderToStaticMarkup(h(Stepper, { steps, current: 2 }));
  assert.equal((html.match(/aria-current="step"/g) ?? []).length, 1);
  assert.equal((html.match(/data-state="done"/g) ?? []).length, 2);
  assert.match(html, /Step 3 of 4/);
  assert.match(html, /sm:hidden/);
  assert.match(html, /hidden[^"]*sm:flex/);
  assert.match(html, /<svg/, "done steps show a check icon");
});
