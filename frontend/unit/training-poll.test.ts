import test from "node:test";
import assert from "node:assert/strict";
import { ApiError } from "../lib/api";
import { isFinal, nextPollDelay, POLL_MS, STOP_CONFIRM_TEXT, stopErrorText } from "../lib/training-poll";
import { trainingDoneMissed, trainingNotStarted, trainingRunning } from "./fixtures";

test("polls only while the project is training", () => {
  assert.equal(nextPollDelay("training", null), POLL_MS);
  assert.equal(nextPollDelay("training", trainingRunning), POLL_MS);
  for (const s of ["paid", "done", "stopped", "failed", "voided", "awaiting_payment", "quoted"]) {
    assert.equal(nextPollDelay(s, trainingRunning), null, s);
  }
});

test("not_started is normal right after paid: keep polling", () => {
  assert.equal(nextPollDelay("training", trainingNotStarted), POLL_MS);
  assert.equal(isFinal(trainingNotStarted), false);
});

test("a final training answer stops the polling", () => {
  assert.equal(nextPollDelay("training", trainingDoneMissed), null);
  assert.equal(isFinal(trainingDoneMissed), true);
  assert.equal(nextPollDelay("training", { status: "failed" }), null);
  assert.equal(nextPollDelay("training", { status: "stopped" }), null);
});

test("stop confirm text is honest about money", () => {
  assert.match(STOP_CONFIRM_TEXT, /pay for the compute used so far/);
  assert.match(STOP_CONFIRM_TEXT, /no success fee/);
  assert.match(STOP_CONFIRM_TEXT, /rest of the hold is released/);
});

test("stop 409 is explained plainly", () => {
  const t = stopErrorText(new ApiError("there is no training running for this project", 409));
  assert.match(t, /nothing to stop/);
  assert.equal(stopErrorText(new ApiError("The server had a problem.", 500)), "The server had a problem.");
});
