import test from "node:test";
import assert from "node:assert/strict";
import { isCurrent, NAV_ITEMS } from "../lib/nav";

test("the nav has only pages that exist", () => {
  assert.deepEqual(NAV_ITEMS.map((n) => n.href), ["/projects", "/account/usage", "/account/billing"]);
  for (const n of NAV_ITEMS) assert.doesNotMatch(n.href + n.label, /key|plan|method|invoice/i);
});

test("a link is current on its page and below it, not on a lookalike", () => {
  assert.equal(isCurrent("/projects", "/projects"), true);
  assert.equal(isCurrent("/projects", "/projects/abc"), true);
  assert.equal(isCurrent("/projects", "/projects-old"), false);
  assert.equal(isCurrent("/account/usage", "/account/billing"), false);
});
