import test from "node:test";
import assert from "node:assert/strict";
import { thinkingMessage } from "../lib/thinking";

test("message follows the elapsed time", () => {
  assert.equal(thinkingMessage(0, true), "The assistant is working…");
  assert.match(thinkingMessage(6, true), /open datasets/);
  assert.match(thinkingMessage(25, true), /Checking the data/);
  assert.match(thinkingMessage(45, true), /up to a minute/);
});

test("later steps do not claim to search for datasets", () => {
  assert.doesNotMatch(thinkingMessage(10, false), /datasets/);
});

test("bad input falls back to the first message", () => {
  assert.equal(thinkingMessage(NaN, true), "The assistant is working…");
  assert.equal(thinkingMessage(-3, true), "The assistant is working…");
});
