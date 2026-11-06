import test from "node:test";
import assert from "node:assert/strict";
import { markWelcomeSeen, pathAfterAuth, welcomeSeen, WELCOME_KEY } from "../lib/welcome";

function memory() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), m };
}

test("the first sign-up goes to the welcome page, once", () => {
  const s = memory();
  assert.equal(pathAfterAuth("signup", "/", s), "/welcome");
  assert.equal(s.m.get(WELCOME_KEY), "1");
  assert.equal(pathAfterAuth("signup", "/", s), "/");
});

test("a login never shows the welcome page", () => {
  const s = memory();
  assert.equal(pathAfterAuth("login", "/projects", s), "/projects");
  assert.equal(welcomeSeen(s), false);
});

test("blocked or throwing storage skips the page and never throws", () => {
  const bad = {
    getItem: () => {
      throw new Error("blocked");
    },
    setItem: () => {
      throw new Error("blocked");
    },
  };
  assert.equal(welcomeSeen(bad), true);
  assert.doesNotThrow(() => markWelcomeSeen(bad));
  assert.equal(pathAfterAuth("signup", "/x", bad), "/x");
  assert.equal(pathAfterAuth("signup", "/x", null), "/x");
});
