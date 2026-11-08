import test from "node:test";
import assert from "node:assert/strict";
import { checkLink, guessAnswerColumn, LINK_HELP } from "../lib/dataset-link";

test("accepts the three known places", () => {
  for (const u of [
    "https://huggingface.co/datasets/scikit-learn/churn-prediction",
    "https://archive.ics.uci.edu/dataset/350/default-of-credit-card-clients",
    "https://archive.ics.uci.edu/dataset/350",
    "https://openml.org/d/40945",
    "https://www.openml.org/d/40945/",
  ]) {
    assert.deepEqual(checkLink(`  ${u} `), { ok: true, url: u });
  }
});

test("refuses look-alikes, plain files, other schemes and credentials with one plain message", () => {
  for (const u of [
    "",
    "not a link",
    "http://huggingface.co/datasets/a/b",
    "file:///etc/passwd",
    "https://huggingface.co.evil.test/datasets/a/b",
    "https://evil-huggingface.co/datasets/a/b",
    "https://user:pw@huggingface.co/datasets/a/b",
    "https://localhost/d/1",
    "https://127.0.0.1/d/1",
    "https://example.com/data.csv",
    "https://huggingface.co/datasets/only-one-part",
    "https://openml.org/search?type=data",
  ]) {
    const r = checkLink(u);
    assert.equal(r.ok, false, u);
    if (!r.ok) assert.ok(r.message === LINK_HELP || r.message === "Paste a link first.", u);
  }
});

test("the suggested answer column wins, then common names, then the last column", () => {
  assert.equal(guessAnswerColumn(["a", "b", "left"], "b"), "b");
  assert.equal(guessAnswerColumn(["a", "Churn", "z"]), "Churn");
  assert.equal(guessAnswerColumn(["a", "z"]), "z");
  assert.equal(guessAnswerColumn(["a", "z"], "missing"), "z");
});
