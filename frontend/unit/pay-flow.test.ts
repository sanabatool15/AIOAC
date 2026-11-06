import test from "node:test";
import assert from "node:assert/strict";
import { ApiError } from "../lib/api";
import { confirmReturn, type ReturnDeps } from "../lib/pay-flow";
import { fx } from "./fixtures";

// ids from the real order body (fixtures.order)
const mem = { paymentId: fx.order.payment_id, projectId: fx.created.id };

function make(over: Partial<ReturnDeps> & { held?: boolean[]; status?: string } = {}) {
  const calls: string[] = [];
  const held = [...(over.held ?? [true])];
  const deps: ReturnDeps = {
    recover: async () => (calls.push("recover"), mem),
    getProjectStatus: async () => (calls.push("status"), over.status ?? "awaiting_payment"),
    authorize: async () => {
      calls.push("authorize");
      const h = held.length > 1 ? held.shift()! : held[0];
      return { held: h, state: h ? "held" : "none" };
    },
    startTraining: async () => {
      calls.push("train");
      return { run_id: "r1", status: "running" };
    },
    forget: () => void calls.push("forget"),
    sleep: async () => void calls.push("sleep"),
    ...over,
  };
  return { deps, calls };
}

test("return page: authorize first, train exactly once only after the server says held", async () => {
  const { deps, calls } = make();
  const o = await confirmReturn(deps);
  assert.deepEqual(o, { kind: "go", projectId: mem.projectId });
  assert.deepEqual(calls, ["recover", "status", "authorize", "train", "forget"]);
});

test("return page: polls when held is false, then trains once", async () => {
  const { deps, calls } = make({ held: [false, false, true] });
  const o = await confirmReturn(deps, () => {}, { waitMs: 0 });
  assert.equal(o.kind, "go");
  assert.equal(calls.filter((c) => c === "authorize").length, 3);
  assert.equal(calls.filter((c) => c === "train").length, 1);
  assert.ok(calls.indexOf("train") > calls.lastIndexOf("authorize"));
});

test("return page: never held means no training call and a plain message", async () => {
  const { deps, calls } = make({ held: [false] });
  const o = await confirmReturn(deps, () => {}, { polls: 3, waitMs: 0 });
  assert.equal(o.kind, "stuck");
  assert.match((o as { text: string }).text, /Nothing has been charged and no training has started/);
  assert.equal(calls.includes("train"), false);
});

test("return page: a project already past payment goes straight back, no authorize, no train", async () => {
  const { deps, calls } = make({ status: "training" });
  const o = await confirmReturn(deps);
  assert.equal(o.kind, "go");
  assert.deepEqual(calls, ["recover", "status"]);
});

test("return page: 409 on train (already started) is fine", async () => {
  const { deps } = make({
    startTraining: async () => {
      throw new ApiError("training already started", 409);
    },
  });
  assert.equal((await confirmReturn(deps)).kind, "go");
});

test("return page: other train errors are shown, not hidden", async () => {
  const { deps } = make({
    startTraining: async () => {
      throw new ApiError("could not start the training job; nothing was charged and your hold is being released", 503);
    },
  });
  const o = await confirmReturn(deps);
  assert.equal(o.kind, "stuck");
  assert.match((o as { text: string }).text, /nothing was charged/);
});

test("return page: no remembered payment gives a stuck message", async () => {
  const { deps } = make({ recover: async () => null });
  assert.equal((await confirmReturn(deps)).kind, "stuck");
});
