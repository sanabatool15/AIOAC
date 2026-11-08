import assert from "node:assert/strict";
import test from "node:test";
import { isNearBottom, shouldFollow } from "../lib/scroll";

test("near the bottom means within the slack of the end of the page", () => {
  assert.equal(isNearBottom({ scrollHeight: 2000, scrollTop: 1100, clientHeight: 800 }), true); // 100px left
  assert.equal(isNearBottom({ scrollHeight: 2000, scrollTop: 1200, clientHeight: 800 }), true); // at the end
  assert.equal(isNearBottom({ scrollHeight: 2000, scrollTop: 0, clientHeight: 800 }), false); // reading the top
});

test("follow the newest message when the person just sent one or was reading the end, never when scrolled up", () => {
  assert.equal(shouldFollow(true, false), true);
  assert.equal(shouldFollow(false, true), true);
  assert.equal(shouldFollow(false, false), false);
});
