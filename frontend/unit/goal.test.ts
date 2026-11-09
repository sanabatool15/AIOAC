import assert from "node:assert/strict";
import { test } from "node:test";
import { passwordInputType, truncateGoal } from "../lib/goal";

test("short goals are unchanged", () => {
  assert.equal(truncateGoal("Predict churn"), "Predict churn");
});

test("long goals are cut on a word and end with an ellipsis", () => {
  const out = truncateGoal("Predict which customers may stop buying from us next month based on their orders", 40);
  assert.equal(out, "Predict which customers may stop buying…");
});

test("a long word with no spaces is cut hard", () => {
  assert.equal(truncateGoal("a".repeat(60), 10), `${"a".repeat(10)}…`);
});

test("whitespace is collapsed", () => {
  assert.equal(truncateGoal("  one\n\ntwo   three "), "one two three");
});

test("password toggle", () => {
  assert.equal(passwordInputType(false), "password");
  assert.equal(passwordInputType(true), "text");
});
