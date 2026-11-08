import test from "node:test";
import assert from "node:assert/strict";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CHAT_REGIONS, ChatLayout, stepChanged } from "../components/shell/chat-layout";
import { PROJECT_STEPS, ProjectStepper, SHORT_STEP_LABELS } from "../components/shell/step-parts";
import { hasEstimateBlock } from "../components/shell/project-chat";
import { isNearBottom, shouldFollow } from "../lib/scroll";
import { STEP_LABELS } from "../lib/status";

function regionOrder(html: string): string[] {
  return [...html.matchAll(/data-region="([a-z]+)"/g)].map((m) => m[1]);
}

test("the page has one fixed order: progress, current step, conversation (newest last)", () => {
  const html = renderToStaticMarkup(
    h(ChatLayout, { progress: h("i", null, "P"), step: h("i", null, "S"), conversation: h("i", null, "C") }),
  );
  assert.deepEqual(regionOrder(html), [...CHAT_REGIONS]);
  assert.ok(html.indexOf(">S<") < html.indexOf(">C<"), "step cards come before the thread");
});

test("the order does not depend on what the step is (data picker or cards)", () => {
  const a = renderToStaticMarkup(h(ChatLayout, { progress: "1", step: h("b", null, "picker"), conversation: "x" }));
  const b = renderToStaticMarkup(h(ChatLayout, { progress: "4", step: h("b", null, "cards"), conversation: "x" }));
  assert.deepEqual(regionOrder(a), regionOrder(b));
});

test("a step change scrolls the step region, the first render does not", () => {
  assert.equal(stepChanged(null, "data"), false);
  assert.equal(stepChanged("data", "data"), false);
  assert.equal(stepChanged("data", "readiness"), true);
});

test("auto-scroll follows a new message only when near the end, or right after sending", () => {
  const atEnd = { scrollHeight: 3000, scrollTop: 2150, clientHeight: 800 };
  const readingTop = { scrollHeight: 3000, scrollTop: 300, clientHeight: 800 };
  assert.equal(shouldFollow(isNearBottom(atEnd), false), true);
  assert.equal(shouldFollow(isNearBottom(readingTop), false), false); // scrolled up: do not move them
  assert.equal(shouldFollow(isNearBottom(readingTop), true), true); // they just sent a message
});

test("the shared estimate note is needed only for blocks that carry estimates", () => {
  assert.equal(hasEstimateBlock({ type: "baseline" }), true);
  assert.equal(hasEstimateBlock({ type: "quote" }), true);
  assert.equal(hasEstimateBlock({ type: "readiness" }), false);
  assert.equal(hasEstimateBlock({ type: "pay" }), false);
});

test("the project stepper lists every step once, marks done steps and the current one, no duplicate list", () => {
  assert.equal(PROJECT_STEPS.length, STEP_LABELS.length);
  assert.equal(SHORT_STEP_LABELS.length, STEP_LABELS.length);
  const html = renderToStaticMarkup(h(ProjectStepper, { index: 3 }));
  assert.equal((html.match(/<li /g) ?? []).length, STEP_LABELS.length);
  assert.equal((html.match(/data-state="done"/g) ?? []).length, 3);
  assert.equal((html.match(/aria-current="step"/g) ?? []).length, 1);
  assert.match(html, new RegExp(`Step 4 of ${STEP_LABELS.length}`)); // small-screen summary
});
