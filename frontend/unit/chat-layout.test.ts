import test from "node:test";
import assert from "node:assert/strict";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { stepChanged } from "../components/shell/chat-layout";
import { InlineChatFrame } from "../components/shell/inline-chat";
import { PROJECT_STEPS, ProjectStepper, SHORT_STEP_LABELS } from "../components/shell/step-parts";
import { hasEstimateBlock } from "../components/shell/project-chat";
import { isNearBottom, shouldFollow } from "../lib/scroll";
import { STEP_LABELS } from "../lib/status";

function frame(canvas: string, thread: string, progress = "P"): string {
  return renderToStaticMarkup(
    h(InlineChatFrame, { projectName: "Goal", canvas: h("i", null, canvas), progress: h("i", null, progress), children: h("i", null, thread) }),
  );
}

test("steps live in their own pane: the canvas holds progress and the step, the thread holds only the conversation", () => {
  const html = frame("STEP", "THREAD");
  const aside = html.slice(html.indexOf("<aside"), html.indexOf("</aside>"));
  assert.ok(aside.includes(">STEP<") && aside.includes(">P<"), "progress and step are in the canvas pane");
  assert.ok(!aside.includes(">THREAD<"), "the thread is not in the canvas pane");
  assert.ok(html.slice(html.indexOf("</aside>")).includes(">THREAD<"), "the thread is in the other pane");
});

test("the chat bar has no Share button, and the layout is the same whatever the step is", () => {
  const a = frame("picker", "x");
  const b = frame("cards", "x");
  assert.ok(!a.includes("Share"));
  assert.equal(a.replace("picker", "#"), b.replace("cards", "#"));
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
  assert.match(html, new RegExp(`Step 4 of ${STEP_LABELS.length}`));
});
