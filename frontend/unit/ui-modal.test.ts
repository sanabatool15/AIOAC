import test from "node:test";
import assert from "node:assert/strict";
import { isTopModal, lockScroll, modalDepth, nextFocusIndex, popModal, pushModal, unlockScroll } from "../components/ui/modal-stack";

test("Esc goes to the top modal only", () => {
  pushModal("a");
  pushModal("b");
  assert.equal(isTopModal("b"), true);
  assert.equal(isTopModal("a"), false);
  popModal("b");
  assert.equal(isTopModal("a"), true, "after the top closes, the one below becomes top");
  popModal("a");
  assert.equal(modalDepth(), 0);
  assert.equal(isTopModal("a"), false);
});

test("pushing the same modal twice does not stack it", () => {
  pushModal("x");
  pushModal("x");
  assert.equal(modalDepth(), 1);
  popModal("x");
});

test("scroll lock is counted and restores the old value", () => {
  const body = { style: { overflow: "auto" } };
  lockScroll(body);
  lockScroll(body);
  assert.equal(body.style.overflow, "hidden");
  unlockScroll(body);
  assert.equal(body.style.overflow, "hidden", "still locked by the other modal");
  unlockScroll(body);
  assert.equal(body.style.overflow, "auto");
  unlockScroll(body); // extra unlock is harmless
  assert.equal(body.style.overflow, "auto");
});

test("focus trap wraps at both ends", () => {
  assert.equal(nextFocusIndex(2, 3, false), 0);
  assert.equal(nextFocusIndex(0, 3, true), 2);
  assert.equal(nextFocusIndex(0, 3, false), 1);
  assert.equal(nextFocusIndex(2, 3, true), 1);
});

test("focus that escaped the dialog is pulled back in", () => {
  assert.equal(nextFocusIndex(-1, 3, false), 0);
  assert.equal(nextFocusIndex(-1, 3, true), 2);
  assert.equal(nextFocusIndex(0, 0, false), -1);
});
