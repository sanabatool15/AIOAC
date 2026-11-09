import test from "node:test";
import assert from "node:assert/strict";
import { activeProjectId, drawerIsOpen, isCurrent, NAV_ITEMS } from "../lib/nav";

test("every nav entry has an icon, so the sidebar and the user menu match", () => {
  for (const n of NAV_ITEMS) assert.ok(n.icon, n.label);
});

test("the active project comes from /c/<id> only", () => {
  assert.equal(activeProjectId("/c/abc"), "abc");
  assert.equal(activeProjectId("/c/abc/extra"), "abc");
  assert.equal(activeProjectId("/c/"), null);
  assert.equal(activeProjectId("/projects/abc"), null);
});

test("the drawer is open only on the page it was opened on", () => {
  assert.equal(drawerIsOpen("/projects", "/projects"), true);
  assert.equal(drawerIsOpen("/projects", "/c/abc"), false);
  assert.equal(drawerIsOpen(null, "/projects"), false);
});

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
